"""Executable offline stress for the real G3 automatic recovery contract.

Default synthetic tests use no provider. Optional private-real-source scenario:
  set MICROGEN_HP_PRIVATE_ACOUSTIC_STAGE to a read-only failed G3 stage dir.
The source, WAVs, transcripts and failed checkpoints must never be committed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

import microgen_batch as batch
from microgen_recovery_registry import (
    REGISTRY_NAME, DECISION_NAME, RecoveryRegistryError,
    classify_log_attempt, digest, verified_stage_hold,
)

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / REGISTRY_NAME
TRACE = (
    "Traceback (most recent call last):\n"
    '  File "microgen_autonomous_acoustic_gate.py", line 905, in audit_stage\n'
    '    raise AutonomousAcousticError("REPAIR_CANDIDATE_BUDGET_HOLD")\n'
    "AutonomousAcousticError: Autonomous acoustic QA blocked: "
    "REPAIR_CANDIDATE_BUDGET_HOLD: three independently grounded "
    "pronunciation risks exceed the finite two-slide repair cap\n"
)


def fixture(tmp_path, salt=""):
    root = tmp_path / ("failed-stage-" + salt)
    root.mkdir()
    shutil.copy2(REGISTRY, root / REGISTRY_NAME)
    (root / "source.pdf").write_bytes(("source-" + salt).encode())
    (root / "microgen_batch.py").write_bytes(("normal-runner-" + salt).encode())
    return root


@pytest.mark.parametrize("trial", range(12))
def test_paid_stage_budget_hold_is_durable_and_never_replayed(tmp_path, trial):
    """12 separate source/runner identities, real subprocess, zero Gemini."""
    root = fixture(tmp_path, str(trial))
    worker = root / "failure.py"
    worker.write_text(
        "import sys\nsys.stderr.write(" + repr(TRACE) + ")\nsys.exit(1)\n",
        encoding="utf8",
    )
    log = tmp_path / ("log-" + str(trial) + ".txt")
    with pytest.raises(RuntimeError, match=(
        "non-retryable AutonomousAcousticError.*"
        "recovery_id=MGA-ACOUSTIC-REPAIR-BUDGET-HOLD")):
        batch.run_subprocess(
            sys.executable, worker.name, root, log,
            "independent two-model acoustic QA",
            gemini_stage=False, retries=trial % 5,
            stage_name="acoustic_qa",
            nonrepeatable_external_stage=True,
        )
    output = log.read_text(encoding="utf8")
    assert output.count(":: attempt 1") == 1
    assert ":: attempt 2" not in output
    decision = json.loads((root / DECISION_NAME).read_text(encoding="utf8"))
    assert decision["accepted_as_qa"] is False
    assert decision["paid_retry_authorized"] is False
    assert decision["publication_allowed"] is False
    assert decision["decision"]["max_unmodified_retries"] == 0
    original_hash = digest(root / DECISION_NAME)
    for _ in range(4):  # reboot-like reconciliation; no process-global state
        assert verified_stage_hold(root, "acoustic_qa") is True
        assert verified_stage_hold(root, "video") is False
    assert digest(root / DECISION_NAME) == original_hash


@pytest.mark.parametrize("mutation", [
    ("source", "source.pdf"),
    ("runner", "microgen_batch.py"),
    ("registry", REGISTRY_NAME),
])
def test_mutated_evidence_aborts_instead_of_reusing_hold(tmp_path, mutation):
    from microgen_recovery_registry import persist_stage_decision
    root = fixture(tmp_path, mutation[0])
    decision = classify_log_attempt(
        "acoustic_qa", TRACE.encode(), registry_folder=root)
    assert decision is not None
    persist_stage_decision(root, decision, attempt_number=1)
    (root / mutation[1]).write_bytes(
        (root / mutation[1]).read_bytes() + b"CHANGED")
    with pytest.raises(RecoveryRegistryError):
        verified_stage_hold(root, "acoustic_qa")


@pytest.mark.parametrize("field", [
    "accepted_as_qa", "paid_retry_authorized", "publication_allowed",
])
def test_tampered_hold_never_becomes_qa_acceptance(tmp_path, field):
    from microgen_recovery_registry import persist_stage_decision
    root = fixture(tmp_path, field)
    decision = classify_log_attempt(
        "acoustic_qa", TRACE.encode(), registry_folder=root)
    persist_stage_decision(root, decision, attempt_number=1)
    receipt = root / DECISION_NAME
    mutated = json.loads(receipt.read_text(encoding="utf8"))
    mutated[field] = True
    receipt.write_text(json.dumps(mutated), encoding="utf8")
    with pytest.raises(RecoveryRegistryError):
        verified_stage_hold(root, "acoustic_qa")


@pytest.mark.parametrize("ending", [
    "TimeoutError: Gemini connection timed out\n",
    "AutonomousAcousticError: all acoustic checks passed\n",
    "SemanticMappingError: unrelated cue changed\n",
])
def test_stale_recognized_trace_cannot_override_current_exception(tmp_path, ending):
    root = fixture(tmp_path, ending[:2])
    injected = TRACE + "Traceback (most recent call last):\n" + ending
    assert classify_log_attempt(
        "acoustic_qa", injected.encode(), registry_folder=root) is None


def test_successful_stage_advances_to_next_worker_without_another_prompt(tmp_path):
    """Two real subprocesses under the production runner's normal success path."""
    root = fixture(tmp_path, "success")
    first = root / "science.py"
    second = root / "acoustic.py"
    first.write_text(
        "from pathlib import Path\n"
        "Path('science.receipt').write_text('verified')\n",
        encoding="utf8",
    )
    second.write_text(
        "from pathlib import Path\n"
        "assert Path('science.receipt').read_text() == 'verified'\n"
        "Path('acoustic.receipt').write_text('verified')\n",
        encoding="utf8",
    )
    log = tmp_path / "successful-stage.log"
    for script, stage_name in (
        ("science.py", "science_qa"),
        ("acoustic.py", "acoustic_qa"),
    ):
        assert batch.run_subprocess(
            sys.executable, script, root, log, stage_name,
            gemini_stage=False, retries=0, stage_name=stage_name,
            nonrepeatable_external_stage=True,
        ) is None
    assert (root / "acoustic.receipt").read_text() == "verified"
    assert not (root / DECISION_NAME).exists()
    assert log.read_text().count(":: attempt 1") == 2
    assert ":: attempt 2" not in log.read_text()


def test_actual_sha_bound_two_reviewer_failure_and_source_repair_no_provider():
    """Use exact authorized HP failed materials, never a fabricated transcript."""
    source = os.environ.get("MICROGEN_HP_PRIVATE_ACOUSTIC_STAGE")
    if not source:
        pytest.skip("private real-source stress requires explicit authorized HP path")
    stage = Path(source)
    assert stage.is_dir() and not stage.is_symlink()
    from microgen_verified_acoustic_replay import valid_trace
    from microgen_tts_acoustic_qa import (
        _input_snapshot, audit_with_recognizer,
    )
    from microgen_autonomous_acoustic_gate import _normalized
    from microgen_reviewed_math_voice import (
        reviewed_math_voice, voice_input_risk_status, preflight_voice_sidecar,
    )
    from text_to_speech_v25 import normalize_scientific_speech
    from microgen_cue_semantic_mapping import numbers
    from microgen_timed_cue_planner import (
        source_grounded_speech_units, _pdf_text_blocks, _lexical_match,
        _require_budget_preflight,
    )
    from microgen_private_dev_policy import MAX_SEMANTIC_SLIDES
    from microgen_quality import check_narration
    import fitz
    import tempfile
    models = ("gemini-3.5-flash", "gemini-3.8-flash")
    traces = list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    assert len(traces) == 1, "must identify exactly one authentic failed receipt"
    trace = valid_trace(traces[0], _input_snapshot(stage, 21), 21, models)
    assert trace is not None, "hash-bound actual Gemini evidence required"
    assert trace["review_required_slides"] == [9, 14, 20]
    to_hash = [stage / "source.pdf", stage / "script_tts.json", traces[0]]
    to_hash += [stage / f"slide{i}.wav" for i in range(1, 22)]
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in to_hash}
    def recognizer(index):
        def blind(wav):
            i = int(wav.stem[5:]) - 1
            return trace["slides"][i]["original_blind_transcripts"][index]
        return blind
    report = audit_with_recognizer(
        stage, _normalized(stage), recognizer(0),
        normalize_scientific_speech, independent_recognizer=recognizer(1),
        recognition_models=models,
    )
    assert report["review_required_slides"] == [9, 14, 20]
    # Offline correction can never retroactively approve original WAVs.
    before = json.loads((stage / "script_tts.json").read_text(encoding="utf8"))
    changed = []
    for row in before["slides"]:
        old = row["tts_text"]
        new = normalize_scientific_speech(reviewed_math_voice(old))
        assert numbers(old) == numbers(new)
        assert reviewed_math_voice(new) == new
        if old != new:
            changed.append(row["slide"])
        row["tts_text"] = new
        row["tts_math_voice_preflight"] = voice_input_risk_status(
            new, normalize_scientific_speech)
    assert changed == [9, 14, 20], changed
    with tempfile.TemporaryDirectory(prefix="G3_PRIVATE_SOURCE_STRESS_") as temp:
        shadow = Path(temp)
        for f in ("source.pdf", "slides.pdf", "slides.tex", "script.txt"):
            shutil.copy2(stage / f, shadow / f)
        for i in range(1, 22):
            shutil.copy2(stage / f"slide{i}.pdf", shadow / f"slide{i}.pdf")
        (shadow / "script_tts.json").write_text(
            json.dumps(before, ensure_ascii=False, indent=2), encoding="utf8")
        check_narration(shadow / "script.txt", shadow / "script_tts.json", 21)
        assert preflight_voice_sidecar(
            shadow, require_policy_binding=True)["status"] == (
                "VOICE_SOURCE_RISK_OFFLINE_PREFLIGHT_PASSED")
        _require_budget_preflight(
            shadow, semantic_limit=MAX_SEMANTIC_SLIDES, max_cues=120)
        unresolved = {}
        with fitz.open(shadow / "slides.pdf") as pdf:
            for i, (row, page) in enumerate(zip(before["slides"], pdf), 1):
                blocks = _pdf_text_blocks(page)
                cues = source_grounded_speech_units(row["tts_text"], blocks)
                _, remaining = _lexical_match(
                    i, cues, blocks, allow_unanchored=True, page=page)
                if remaining:
                    unresolved[i] = [n for n, _ in remaining]
        assert unresolved == {16: [2], 21: [4]}, unresolved
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in to_hash} == originals
