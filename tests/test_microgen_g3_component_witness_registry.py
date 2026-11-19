"""V6 executable registry for real bounded G3 third-Gemini math witness.

All subprocesses here are offline simulated failure drivers; none contacts
Gemini. Real original private 21-WAV model evidence is covered separately.
"""
from pathlib import Path
import json
import shutil
import sys

import pytest
import microgen_batch as batch
from microgen_recovery_registry import (
    REGISTRY_NAME,DECISION_NAME,load_registry,
    classify_log_attempt,classify_runtime_error,
)

REPO=Path(__file__).resolve().parents[1]

CASES=[
    (
        "VerifiedAcousticReplayError",
        "COMPONENT_WITNESS_MATHEMATICS_HOLD: real third disagreed",
        "MGA-G3-COMPONENT-MATH-WITNESS-DISSENT",
        "DETERMINISTIC_HOLD",
    ),
    (
        "RuntimeError",
        "G3_COMPONENT_THIRD_GEMINI_UNAVAILABLE: third model exhausted",
        "MGA-G3-COMPONENT-MATH-WITNESS-UNAVAILABLE",
        "PAUSED_EXTERNAL_DEPENDENCY",
    ),
    (
        "VerifiedAcousticReplayError",
        "COMPONENT_WITNESS_SCOPE_HOLD: already spent fresh grant",
        "MGA-G3-COMPONENT-MATH-WITNESS-SCOPE",
        "DETERMINISTIC_HOLD",
    ),
    (
        "VerifiedAcousticReplayError",
        "Historical mathematics disagreement still material; no paid replay",
        "MGA-G3-COMPONENT-MATH-WITNESS-INELIGIBLE",
        "DETERMINISTIC_HOLD",
    ),
]


def stage_for(tmp_path):
    stage=tmp_path/"2.7"
    stage.mkdir(parents=True)
    shutil.copy2(REPO/REGISTRY_NAME,stage/REGISTRY_NAME)
    (stage/"microgen_batch.py").write_bytes(b"offline runner source")
    (stage/"source.pdf").write_bytes(b"offline source PDF")
    return stage


@pytest.mark.parametrize("exception,message,identifier,status",CASES)
def test_original_terminal_traceback_classifies_exactly(
        tmp_path,exception,message,identifier,status):
    stage=stage_for(tmp_path)
    registry=load_registry(stage)
    assert registry["schema_version"]==6
    assert {x["id"] for x in registry["entries"]}.issuperset(
        {item[2] for item in CASES})
    sample=(
        "Traceback (most recent call last):\n"
        '  File "microgen_verified_acoustic_replay.py", line 220, in main\n'
        f"{exception}: {message}\n"
    ).encode()
    decision=classify_log_attempt(
        "acoustic_qa",sample,registry_folder=stage)
    assert decision is not None
    assert decision["failure_id"]==identifier
    assert decision["disposition"]==status
    assert decision["max_unmodified_retries"]==0
    assert classify_log_attempt(
        "narration",sample,registry_folder=stage) is None


@pytest.mark.parametrize("exception,message,identifier,status",CASES)
@pytest.mark.parametrize("trial",range(3))
def test_normal_driver_never_replays_a_third_witness_failure(
        tmp_path,exception,message,identifier,status,trial):
    stage=stage_for(tmp_path)
    worker=stage/"failed_paid_third.py"
    worker.write_text(
        "import sys\n"
        "sys.stderr.write('Traceback (most recent call last):\\n"
        f"{exception}: {message}\\n')\n"
        "sys.exit(1)\n",encoding="utf8")
    log=tmp_path/"failure.log"
    if status=="PAUSED_EXTERNAL_DEPENDENCY":
        expected="VERIFIED_EXTERNAL_DEPENDENCY_HOLD"
    else:
        expected="failed with non-retryable"
    with pytest.raises(RuntimeError,match=expected) as exc:
        batch.run_subprocess(
            sys.executable,worker.name,stage,log,
            "independent two-model acoustic QA",
            gemini_stage=False,retries=4,stage_name="acoustic_qa",
            nonrepeatable_external_stage=True)
    assert log.read_text(encoding="utf8").count(":: attempt 1")==1
    assert ":: attempt 2" not in log.read_text(encoding="utf8")
    if status=="DETERMINISTIC_HOLD":
        assert (stage/DECISION_NAME).is_file()
        assert json.loads((stage/DECISION_NAME).read_text())[
            "decision"]["failure_id"]==identifier
    else:
        assert not (stage/DECISION_NAME).exists()
        parent=classify_runtime_error(
            "acoustic_qa",exc.value,registry_folder=stage)
        assert parent["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"


@pytest.mark.parametrize("sample",[
    "Source text quotes COMPONENT_WITNESS_MATHEMATICS_HOLD",
    "Traceback (most recent call last):\n"
        "  VerifiedAcousticReplayError: COMPONENT_WITNESS_MATHEMATICS_HOLD",
    "Traceback (most recent call last):\n"
        "VerifiedAcousticReplayError: COMPONENT_WITNESS_MATHEMATICS_HOLD\n"
        "Traceback (most recent call last):\nValueError: unrelated",
    "Traceback (most recent call last):\n"
        "ValueError: COMPONENT_WITNESS_MATHEMATICS_HOLD",
    "Traceback (most recent call last):\n"
        "AutonomousAcousticError: G3_COMPONENT_THIRD_GEMINI_UNAVAILABLE",
])
def test_log_spoofing_and_wrong_exception_are_not_known_recoveries(
        tmp_path,sample):
    stage=stage_for(tmp_path)
    assert classify_log_attempt(
        "acoustic_qa",sample.encode(),registry_folder=stage) is None



@pytest.mark.parametrize("state,exception,marker",[
    ({"status":"THIRD_GEMINI_REVIEWER_UNAVAILABLE"},
     RuntimeError,"G3_COMPONENT_THIRD_GEMINI_UNAVAILABLE"),
    ({"status":"MATH_WITNESS_UNRESOLVED",
      "attempts":[{"status":"WITNESS_UNAVAILABLE"}]},
     RuntimeError,"G3_COMPONENT_THIRD_GEMINI_UNAVAILABLE"),
    ({"status":"MATH_WITNESS_UNRESOLVED",
      "attempts":[{"status":"WITNESS_DISAGREES_OR_INVALID"}]},
     __import__("microgen_verified_acoustic_replay").VerifiedAcousticReplayError,
     "COMPONENT_WITNESS_MATHEMATICS_HOLD"),
    ({"status":"PAID_WITNESS_SCOPE_UNAUTHORIZED"},
     __import__("microgen_verified_acoustic_replay").VerifiedAcousticReplayError,
     "COMPONENT_WITNESS_SCOPE_HOLD"),
    ({"status":"PAID_WITNESS_ALREADY_RESERVED_OR_INVALID"},
     __import__("microgen_verified_acoustic_replay").VerifiedAcousticReplayError,
     "COMPONENT_WITNESS_SCOPE_HOLD"),
    (None,
     __import__("microgen_verified_acoustic_replay").VerifiedAcousticReplayError,
     "COMPONENT_WITNESS_MATHEMATICS_HOLD"),
])
def test_provider_outage_never_misclassified_as_mathematics_or_paid_retry(
        state,exception,marker):
    from microgen_verified_acoustic_replay import _third_component_witness_hold
    answer=_third_component_witness_hold(state)
    assert isinstance(answer,exception)
    assert str(answer).startswith(marker)
    assert "source-bound" not in str(answer).lower()
