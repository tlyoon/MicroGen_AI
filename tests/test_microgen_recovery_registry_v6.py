"""V6 production registry: historical recognition, QA holds, restarts and locks.

No model/API/paid work. Actual historical traceback is separately replayed
read-only on the authorized HP host, not bundled with public test fixtures.
"""
import json
from pathlib import Path
import shutil
import sys

import pytest

import microgen_batch as batch
from microgen_recovery_registry import (
    REGISTRY_NAME, DECISION_NAME, RecoveryRegistryError,
    classify_log_attempt, digest, load_registry, persist_stage_decision,
)


REGISTRY = Path(__file__).resolve().parents[1] / REGISTRY_NAME
ACOUSTIC = (
    "Traceback (most recent call last):\n"
    '  File "microgen_autonomous_acoustic_gate.py", line 883, in main\n'
    '    raise AutonomousAcousticError("Autonomous acoustic QA blocked")\n'
    "AutonomousAcousticError: Autonomous acoustic QA blocked: "
    "ASR_DISAGREEMENT_HOLD: independent evidence requires resolution\n"
)
MAPPING = (
    "Traceback (most recent call last):\n"
    '  File "microgen_timed_cue_planner.py", line 45\n'
    "SemanticMappingError: Empty or unsupported source-PDF mapping\n"
)


def stage(tmp_path):
    root = tmp_path / "2.7"
    root.mkdir()
    (root / REGISTRY_NAME).write_bytes(REGISTRY.read_bytes())
    (root / "source.pdf").write_bytes(b"exact-source-only-synthetic-fixture")
    (root / "microgen_batch.py").write_bytes(b"immutable-runner-synthetic")
    return root


def test_prior_acoustic_historical_failure_signature_fails_closed(tmp_path):
    root=stage(tmp_path)
    decision=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                                  registry_folder=root)
    assert decision["failure_id"]=="MGA-20261116-ACOUSTIC-ASR"
    assert decision["category"]=="scientific_qa"
    assert decision["disposition"]=="DETERMINISTIC_HOLD"
    assert decision["max_unmodified_retries"]==0
    assert decision["registry_sha256"]==digest(root/REGISTRY_NAME)


def test_historical_semantic_mapping_and_wrong_stage(tmp_path):
    root=stage(tmp_path)
    x=classify_log_attempt("tts",MAPPING.encode(),registry_folder=root)
    assert x["failure_id"]=="MGA-SOURCE-SEMANTIC-MAPPING"
    assert classify_log_attempt("narration",MAPPING.encode(),
                                registry_folder=root) is None


@pytest.mark.parametrize("output",[
    b"A PDF says AutonomousAcousticError: ASR_DISAGREEMENT_HOLD",
    b"AutonomousAcousticError: ASR_DISAGREEMENT_HOLD",
    b"Traceback (most recent call last):\nTimeoutError: service stalled\n",
    b"Traceback (most recent call last):\n"
    b"AutonomousAcousticError: acoustic discrepancy independently closed\n",
    b"Traceback (most recent call last):\n"
    b"SomeUnknownScienceError: made-up fault\n",
])
def test_unknown_transient_or_untrusted_words_never_grant_known_hold(tmp_path,output):
    root=stage(tmp_path)
    assert classify_log_attempt("acoustic_qa",output,
                                registry_folder=root) is None


def test_old_traceback_cannot_override_latest_true_exception(tmp_path):
    root=stage(tmp_path)
    combined=(ACOUSTIC + "Traceback (most recent call last):\n"
              + "TimeoutError: network unavailable\n")
    assert classify_log_attempt("acoustic_qa",combined.encode(),
                                registry_folder=root) is None


def test_real_qa_hold_receipt_persists_restart_without_pass_or_paid_scope(tmp_path):
    root=stage(tmp_path)
    decision=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                                  registry_folder=root)
    one=persist_stage_decision(root,decision,attempt_number=1)
    assert one["accepted_as_qa"] is False
    assert one["paid_retry_authorized"] is False
    assert one["publication_allowed"] is False
    assert one["next_eligible_operation"].startswith("HOLD")
    receipt=root/DECISION_NAME
    assert receipt.is_file()
    raw=receipt.read_bytes()
    assert persist_stage_decision(root,decision,attempt_number=1)==one
    assert receipt.read_bytes()==raw
    assert one["source_sha256"]==digest(root/"source.pdf")
    assert one["batch_runner_sha256"]==digest(root/"microgen_batch.py")
    with pytest.raises(RecoveryRegistryError,match="different identity"):
        persist_stage_decision(root,decision,attempt_number=2)
    assert receipt.read_bytes()==raw


def test_corrupted_receipt_fails_closed(tmp_path):
    root=stage(tmp_path)
    x=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                           registry_folder=root)
    (root/DECISION_NAME).write_bytes(b"{bad-json")
    with pytest.raises(RecoveryRegistryError,match="Corrupted"):
        persist_stage_decision(root,x,attempt_number=1)


def test_missing_and_corrupted_registry_never_falls_back_to_fake_approval(tmp_path):
    root=stage(tmp_path)
    (root/REGISTRY_NAME).unlink()
    with pytest.raises(RecoveryRegistryError):
        load_registry(root)
    (root/REGISTRY_NAME).write_text('{"schema_version":6,"entries":[]}')
    with pytest.raises(RecoveryRegistryError):
        load_registry(root)


def test_duplicate_signatures_or_changed_publication_policy_are_rejected(tmp_path):
    root=stage(tmp_path)
    data=json.loads((root/REGISTRY_NAME).read_text())
    data["entries"].append(data["entries"][0])
    (root/REGISTRY_NAME).write_text(json.dumps(data))
    with pytest.raises(RecoveryRegistryError):
        load_registry(root)
    data["entries"].pop()
    data["entries"][0]["publication_allowed"]=True
    (root/REGISTRY_NAME).write_text(json.dumps(data))
    with pytest.raises(RecoveryRegistryError):
        load_registry(root)


def test_actual_normal_runner_selects_known_recovery_and_avoids_retries(tmp_path):
    root=stage(tmp_path)
    worker=root/"fake_acoustic_failure.py"
    worker.write_text(
        "import sys\n"
        "sys.stderr.write("+repr(ACOUSTIC)+")\n"
        "sys.exit(1)\n",encoding="utf8")
    log=tmp_path/"runner.log"
    with pytest.raises(RuntimeError,match=
                       "non-retryable AutonomousAcousticError.*recovery_id="):
        batch.run_subprocess(
            sys.executable,worker.name,root,log,"independent acoustic QA",
            gemini_stage=False,retries=3,stage_name="acoustic_qa",
        )
    assert log.read_text().count("attempt 1") == 1
    assert "attempt 2" not in log.read_text()
    receipt=json.loads((root/DECISION_NAME).read_text())
    assert receipt["decision"]["failure_id"]=="MGA-20261116-ACOUSTIC-ASR"
    assert receipt["accepted_as_qa"] is False


def test_successful_stage_returns_immediately_for_next_eligible_stage(tmp_path):
    root=stage(tmp_path)
    worker=root/"successful_stage.py"
    worker.write_text("print('verified work complete')\n",encoding="utf8")
    log=tmp_path/"success.log"
    assert batch.run_subprocess(
        sys.executable,worker.name,root,log,"mock verified stage",
        gemini_stage=False,retries=2,stage_name="acoustic_qa",
    ) is None
    assert "verified work complete" in log.read_text()
    assert not (root/DECISION_NAME).exists()


def test_crash_after_hold_receipt_before_checkpoint_blocks_restart(tmp_path):
    from microgen_recovery_registry import verified_stage_hold
    root=stage(tmp_path)
    decision=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                                  registry_folder=root)
    persist_stage_decision(root,decision,attempt_number=1)
    # No batch checkpoint was written: a crash in the narrow window after
    # writing recovery evidence cannot authorize unchanged paid QA again.
    assert not (root/".microgen_checkpoint.json").exists()
    assert verified_stage_hold(root,"acoustic_qa")
    assert not verified_stage_hold(root,"figure_extraction")
    assert verified_stage_hold(root,"acoustic_qa")


def test_stale_source_or_updated_runner_never_reuses_hold_as_accepted(tmp_path):
    from microgen_recovery_registry import verified_stage_hold
    root=stage(tmp_path)
    decision=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                                  registry_folder=root)
    persist_stage_decision(root,decision,attempt_number=1)
    (root/"source.pdf").write_bytes(b"changed-source")
    with pytest.raises(RecoveryRegistryError, match="changed"):
        verified_stage_hold(root,"acoustic_qa")
    (root/"source.pdf").write_bytes(b"exact-source-only-synthetic-fixture")
    (root/"microgen_batch.py").write_bytes(b"changed-runner")
    with pytest.raises(RecoveryRegistryError, match="changed"):
        verified_stage_hold(root,"acoustic_qa")


def test_tamper_qa_pass_or_retry_grant_rejected_on_restart(tmp_path):
    from microgen_recovery_registry import verified_stage_hold
    root=stage(tmp_path)
    decision=classify_log_attempt("acoustic_qa",ACOUSTIC.encode(),
                                  registry_folder=root)
    original=persist_stage_decision(root,decision,attempt_number=1)
    for field, value in (
        ("accepted_as_qa",True),
        ("paid_retry_authorized",True),
        ("publication_allowed",True),
    ):
        changed=dict(original)
        changed[field]=value
        (root/DECISION_NAME).write_text(json.dumps(changed))
        with pytest.raises(RecoveryRegistryError):
            verified_stage_hold(root,"acoustic_qa")
    (root/DECISION_NAME).write_text(json.dumps(original))
    assert verified_stage_hold(root,"acoustic_qa")


def test_known_scientific_hold_wins_over_simultaneous_gemini_circuit(
        tmp_path,monkeypatch):
    root=stage(tmp_path)
    worker=root/"failure_with_circuit.py"
    worker.write_text(
        "import sys\nsys.stderr.write("+repr(ACOUSTIC)+")\nsys.exit(1)\n",
        encoding="utf8")
    calls=[]
    def fake_wait(lease=None):
        calls.append("before_first_submission")
    monkeypatch.setattr(batch,"wait_for_gemini_circuit",fake_wait)
    monkeypatch.setattr(batch,"circuit_is_open",
                        lambda:(True,{"type":"rate_limit"}))
    with pytest.raises(RuntimeError,match="recovery_id=MGA-20261116-ACOUSTIC-ASR"):
        batch.run_subprocess(
            sys.executable,worker.name,root,tmp_path/"circuit.log",
            "independent acoustic QA",
            gemini_stage=True,retries=5,stage_name="acoustic_qa",
        )
    # Initial circuit preflight is not a paid call; there must be NO
    # second sleep/retry after an independently grounded QA hold.
    assert calls==["before_first_submission"]
    assert (root/DECISION_NAME).is_file()


def test_newly_discovered_checkpoint_corruption_is_registered_for_future_reuse(
        tmp_path):
    root=stage(tmp_path)
    traceback=(
        "Traceback (most recent call last):\n"
        '  File "microgen_batch.py", line 180, in load_checkpoint\n'
        "CheckpointIntegrityError: AMBIGUOUS_CHECKPOINT_HOLD: malformed saved state\n"
    )
    rule=classify_log_attempt("checkpoint",traceback.encode("utf8"),
                              registry_folder=root)
    assert rule is not None
    assert rule["failure_id"]=="MGA-CHECKPOINT-CORRUPTION"
    assert rule["category"]=="orchestration"
    assert rule["handler"]=="microgen_batch.load_checkpoint"
    assert rule["disposition"]=="DETERMINISTIC_HOLD"
    assert rule["max_unmodified_retries"]==0
    assert classify_log_attempt("acoustic_qa",traceback.encode("utf8"),
                                registry_folder=root) is None

BUDGET_ACOUSTIC = (
    "Traceback (most recent call last):\n"
    '  File "microgen_autonomous_acoustic_gate.py", line 905, in audit_stage\n'
    '    raise AutonomousAcousticError("REPAIR_CANDIDATE_BUDGET_HOLD")\n'
    "AutonomousAcousticError: Autonomous acoustic QA blocked: "
    "REPAIR_CANDIDATE_BUDGET_HOLD: independent evidence requires bounded "
    "resolution; do not rewrite or replay original speech\n"
)


def test_three_candidate_acoustic_hold_is_known_scientific_not_uncertain_paid(tmp_path):
    root=stage(tmp_path)
    decision=classify_log_attempt(
        "acoustic_qa",BUDGET_ACOUSTIC.encode("utf8"),registry_folder=root)
    assert decision["failure_id"]=="MGA-ACOUSTIC-REPAIR-BUDGET-HOLD"
    assert decision["category"]=="scientific_qa"
    assert decision["disposition"]=="DETERMINISTIC_HOLD"
    assert decision["max_unmodified_retries"]==0
    assert classify_log_attempt(
        "tts",BUDGET_ACOUSTIC.encode("utf8"),registry_folder=root) is None
    worker=root/"three_candidate_acoustic.py"
    worker.write_text(
        "import sys\nsys.stderr.write("+repr(BUDGET_ACOUSTIC)+")\nsys.exit(1)\n",
        encoding="utf8")
    log=tmp_path/"actual_paid_stage.log"
    with pytest.raises(RuntimeError,match=(
        "non-retryable AutonomousAcousticError.*"
        "recovery_id=MGA-ACOUSTIC-REPAIR-BUDGET-HOLD")):
        batch.run_subprocess(
            sys.executable,worker.name,root,log,
            "independent two-model acoustic QA",
            gemini_stage=False,retries=3,stage_name="acoustic_qa",
            nonrepeatable_external_stage=True,
        )
    assert log.read_text().count("attempt 1")==1
    assert "attempt 2" not in log.read_text()
    from microgen_recovery_registry import verified_stage_hold
    assert verified_stage_hold(root,"acoustic_qa")
    receipt=json.loads((root/DECISION_NAME).read_text(encoding="utf8"))
    assert receipt["decision"]["failure_id"]==decision["failure_id"]
    assert receipt["accepted_as_qa"] is False
    assert receipt["paid_retry_authorized"] is False
    assert receipt["publication_allowed"] is False
    assert receipt["next_eligible_operation"]=="HOLD_SAME_STAGE_UNTIL_VERIFIED_NEW_EVIDENCE"


def test_repair_budget_is_not_matched_from_untrusted_pdfs_or_old_tracebacks(tmp_path):
    root=stage(tmp_path)
    for body in (
        BUDGET_ACOUSTIC.split("Traceback (most recent call last):\n")[1],
        "A textbook says REPAIR_CANDIDATE_BUDGET_HOLD",
        BUDGET_ACOUSTIC+
        "Traceback (most recent call last):\n"
        "TimeoutError: Gemini unavailable\n",
        BUDGET_ACOUSTIC.replace(
            "Autonomous acoustic QA blocked: ", "Acoustic repair passed: "),
        BUDGET_ACOUSTIC.replace(
            "AutonomousAcousticError:", "DifferentAcousticError:"),
    ):
        assert classify_log_attempt(
            "acoustic_qa",body.encode("utf8"),registry_folder=root) is None
