"""Known finite acoustic reviewer outage => typed external hold, never a fake QA defect.

Offline actual runner injection. Optional private HP real traceback/21-WAV test:
MICROGEN_HP_PRIVATE_REVIEWER_OUTAGE_STAGE=<exact failed G3 outage stage>.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys

import pytest

import microgen_batch as batch
from microgen_recovery_registry import (
    REGISTRY_NAME, DECISION_NAME, load_registry,
    classify_log_attempt, classify_runtime_error,
)

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / REGISTRY_NAME
ACTUAL_EXHAUSTION = (
    "Traceback (most recent call last):\n"
    '  File "microgen_autonomous_acoustic_gate.py", line 901, in audit_stage\n'
    "AutonomousAcousticError: Independent acoustic transcription "
    "unavailable for model pass(es) [0, 1]\n"
    "\nThe above exception was the direct cause of the following exception:\n\n"
    "Traceback (most recent call last):\n"
    '  File "microgen_autonomous_acoustic_gate.py", line 989, in audit_stage\n'
    "AutonomousAcousticError: Autonomous acoustic QA blocked: "
    "Independent acoustic transcription unavailable for model pass(es) [0, 1]\n"
)


def sandbox(tmp_path, i):
    stage = tmp_path / ("stage-" + str(i))
    stage.mkdir()
    shutil.copy2(REGISTRY, stage / REGISTRY_NAME)
    (stage / "source.pdf").write_bytes(("source" + str(i)).encode())
    (stage / "microgen_batch.py").write_bytes(("runner" + str(i)).encode())
    return stage


def test_real_failure_signature_is_an_external_dependency_not_acoustic_qa_pass(tmp_path):
    stage=sandbox(tmp_path,"signature")
    assert len(load_registry(stage)["entries"]) >= 18
    child=classify_log_attempt(
        "acoustic_qa",ACTUAL_EXHAUSTION.encode(),registry_folder=stage)
    assert child["failure_id"]=="MGA-ACOUSTIC-REVIEWERS-UNAVAILABLE"
    assert child["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    assert child["category"]=="infrastructure"
    assert child["max_unmodified_retries"]==0
    assert classify_log_attempt(
        "narration",ACTUAL_EXHAUSTION.encode(),registry_folder=stage) is None


@pytest.mark.parametrize("trial",range(8))
def test_real_runner_stops_unavailable_paid_acoustic_once_with_typed_hold(tmp_path,trial):
    stage=sandbox(tmp_path,trial)
    worker=stage/"reviewers_unavailable.py"
    worker.write_text(
        "import sys\nsys.stderr.write("+repr(ACTUAL_EXHAUSTION)+")\nsys.exit(1)\n",
        encoding="utf8")
    log=tmp_path/("review-"+str(trial)+".log")
    with pytest.raises(RuntimeError,match=(
            "VERIFIED_EXTERNAL_DEPENDENCY_HOLD:.*"
            "recovery_id=MGA-ACOUSTIC-REVIEWERS-UNAVAILABLE")) as result:
        batch.run_subprocess(
            sys.executable,worker.name,stage,log,
            "independent two-model acoustic QA",
            gemini_stage=False,retries=4,stage_name="acoustic_qa",
            nonrepeatable_external_stage=True)
    assert log.read_text(encoding="utf8").count(":: attempt 1")==1
    assert ":: attempt 2" not in log.read_text(encoding="utf8")
    # An external service outage is not a permanent scientific defect.
    assert not (stage/DECISION_NAME).exists()
    rule=classify_runtime_error(
        "acoustic_qa",result.value,registry_folder=stage)
    assert rule["failure_id"]=="MGA-CHILD-EXTERNAL-DEPENDENCY-HOLD"
    assert rule["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    assert rule["max_unmodified_retries"]==0


@pytest.mark.parametrize("payload",[
    ACTUAL_EXHAUSTION.split("Traceback (most recent call last):\n")[1],
    "The lecture claims independent acoustic transcription unavailable",
    ACTUAL_EXHAUSTION+"Traceback (most recent call last):\n"
        "TimeoutError: internet disconnected\n",
    ACTUAL_EXHAUSTION.replace("unavailable","available"),
    "Traceback (most recent call last):\n"
        "SomeOtherError: Independent acoustic transcription unavailable "
        "for model pass(es) [0, 1]\n",
])
def test_unknown_or_embedded_reviewer_string_is_not_a_known_service_hold(tmp_path,payload):
    stage=sandbox(tmp_path,"negative")
    assert classify_log_attempt(
        "acoustic_qa",payload.encode(),registry_folder=stage) is None


def test_parent_outage_marker_cannot_authorize_a_retry_or_pass(tmp_path):
    stage=sandbox(tmp_path,"runtime")
    ordinary=RuntimeError(
        "VERIFIED_EXTERNAL_DEPENDENCY_HOLD: acoustic reviewers exhausted; "
        "recovery_id=MGA-ACOUSTIC-REVIEWERS-UNAVAILABLE")
    classified=classify_runtime_error(
        "acoustic_qa",ordinary,registry_folder=stage)
    assert classified["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    assert classified["max_unmodified_retries"]==0
    for bad in (
        RuntimeError("AMBIGUOUS_PROVIDER_STAGE_HOLD: still unverified"),
        RuntimeError("VERIFIED_EXTERNAL_DEPENDENCY_HOLD (no colon)"),
        RuntimeError("x VERIFIED_EXTERNAL_DEPENDENCY_HOLD: pasted"),
    ):
        got=classify_runtime_error("acoustic_qa",bad,registry_folder=stage)
        assert got is None or got["failure_id"]!="MGA-CHILD-EXTERNAL-DEPENDENCY-HOLD"


def test_exact_hp_failed_two_pass_review_preserves_all_21_wavs():
    stage_env=os.environ.get("MICROGEN_HP_PRIVATE_REVIEWER_OUTAGE_STAGE")
    if not stage_env:
        pytest.skip("real HP failure accessible only in authorized private test")
    stage=Path(stage_env)
    assert stage.is_dir() and not stage.is_symlink()
    log=stage.parent/"2.7.log"
    assert log.is_file()
    raw=log.read_bytes()
    at=raw.rfind(b"===== independent two-model acoustic QA")
    assert at>=0
    tail=raw[at:]
    assert b"FINITE_GEMINI_REVIEWER_FALLBACK_EXHAUSTED" in tail
    assert tail.count(b"key slot")>=8
    child=classify_log_attempt(
        "acoustic_qa",tail,registry_folder=REPO)
    assert child["failure_id"]=="MGA-ACOUSTIC-REVIEWERS-UNAVAILABLE"
    assert child["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    checkpoint=json.loads(
        (stage/".microgen_checkpoint.json").read_text(encoding="utf8"))
    assert checkpoint["inflight_provider_stage"]["stage"]=="acoustic_qa"
    assert checkpoint["last_error"]["paid_retry_authorized"] is False
    assert "acoustic_qa" not in checkpoint["completed"]
    wavs=[stage/f"slide{i}.wav" for i in range(1,22)]
    assert all(p.is_file() and p.stat().st_size>1000 for p in wavs)
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [stage/"source.pdf",stage/"script_tts.json",*wavs]}
    blocked=list(stage.glob(".microgen_acoustic_blocked_*.json"))
    assert len(blocked)==1
    receipt=json.loads(blocked[0].read_text(encoding="utf8"))
    assert receipt["review_required_slides"]==list(range(1,22))
    assert receipt["review_categories"]["recognition_unavailable"]==list(range(1,22))
    assert receipt["unavailable_recognizer_passes"]==[0,1]
    assert receipt["root_cause_family"]=="INDEPENDENT_RECOGNIZER_UNAVAILABLE"
    assert receipt["recognition_models"]==["gemini-3.5-flash","gemini-3.8-flash"]
    assert receipt.get("accepted_for_video",False) is False
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [stage/"source.pdf",stage/"script_tts.json",*wavs]}==before
