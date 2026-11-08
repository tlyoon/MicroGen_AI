"""Historical blocker replay against the production stage runner (offline).

Proves that source/semantic QA failures never consume repeated paid-stage
attempts, whereas previously unseen transient driver failures retain bounded
retries. These are not proofs of real lecture acceptance.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import microgen_batch as batch


def _run(stage: Path, text_by_attempt, *, retries=3):
    log = stage / "stage.log"
    calls = []

    def execute(argv, *, cwd, stdout, stderr, text, timeout):
        calls.append((list(argv), cwd))
        status, content = text_by_attempt[min(len(calls) - 1, len(text_by_attempt)-1)]
        stdout.write(content)
        stdout.flush()
        return SimpleNamespace(returncode=status)

    with patch.object(batch.subprocess, "run", side_effect=execute), patch.object(
        batch.time, "sleep"
    ):
        try:
            batch.run_subprocess(
                "python", "text_to_speech_v25.py", stage, log, "tts",
                gemini_stage=False, retries=retries,
            )
            error = None
        except Exception as exc:
            error = exc
    return calls, error, log.read_text(encoding="utf-8")


@pytest.mark.parametrize("exception_class", [
    "microgen_timed_cue_planner.CuePlanningError",
    "SemanticMappingError",
    "PronunciationPreflightError",
    "HighlightContractError",
])
def test_known_deterministic_qa_replay_stops_after_one_attempt(
        tmp_path: Path, exception_class: str):
    script_stdout = (
        "Traceback (most recent call last):\n"
        "  File \"text_to_speech_v25.py\", line 9\n"
        f"{exception_class}: rejected source-bound proposal\n"
    )
    calls, error, logged = _run(
        tmp_path, [(1, script_stdout)], retries=5,
    )
    assert len(calls) == 1
    assert isinstance(error, RuntimeError)
    assert "non-retryable" in str(error)
    assert "after 1 attempt(s)" in str(error)
    assert "attempt 2" not in logged


def test_unknown_driver_failure_can_recover_with_existing_bounded_retry(tmp_path):
    calls, error, logged = _run(
        tmp_path,
        [(1, "connection refused by temporary remote provider\n"),
         (0, "stage completed successfully\n")],
        retries=2,
    )
    assert error is None
    assert len(calls) == 2
    assert "attempt 2" in logged


def test_no_stage_retry_allowed_stops_unknown_failure_once(tmp_path):
    calls, error, _ = _run(
        tmp_path, [(1, "unclassified error\n")], retries=0,
    )
    assert len(calls) == 1
    assert isinstance(error, RuntimeError)
    assert "after 1 attempt" in str(error)


def test_old_checkpoint_errors_do_not_poison_new_successful_attempt(tmp_path):
    log = tmp_path / "stage.log"
    log.write_text(
        "microgen_timed_cue_planner.CuePlanningError: OLD FAILURE\n",
        encoding="utf-8",
    )
    calls, error, logged = _run(tmp_path, [(0, "completed\n")])
    assert error is None
    assert len(calls) == 1
    assert "OLD FAILURE" in logged


def test_private_source_sentence_is_not_misclassified_as_exception(tmp_path):
    calls, error, logged = _run(
        tmp_path,
        [(1, "Narration quotes CuePlanningError: as a phrase, not a traceback\n"),
         (0, "completed\n")], retries=2,
    )
    assert error is None
    assert len(calls) == 2
    assert "attempt 2" in logged


def test_identical_deterministic_failure_hold_survives_checkpoint_restart(
        tmp_path, monkeypatch):
    import microgen_quality as quality
    # Minimum real files used by the TTS fingerprint. No provider request.
    for name in ("script_tts.json", "text_to_speech_v25.py", "microgen_batch.py"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    monkeypatch.setenv("MICROGEN_TIMED_CUES", "1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    cp = {"completed": {}, "last_error": {
        "stage": "tts",
        "recovery_disposition": "DETERMINISTIC_HOLD",
        "input_fingerprint": quality.dependency_fingerprint(tmp_path, "tts"),
        "recovery_runner_sha256": quality.sha256(tmp_path / "microgen_batch.py"),
    }}
    saved = tmp_path / ".microgen_checkpoint.json"
    batch.save_checkpoint(saved, cp)
    reloaded = batch.load_checkpoint(saved)
    assert batch.unchanged_failure_hold(reloaded, "tts", tmp_path)
    assert not batch.unchanged_failure_hold(reloaded, "slides", tmp_path)
    # No artificial reset on a new invocation.
    assert batch.unchanged_failure_hold(batch.load_checkpoint(saved), "tts", tmp_path)

    # A newly authorized semantic budget is a meaningful distinct input.
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "8")
    assert not batch.unchanged_failure_hold(reloaded, "tts", tmp_path)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    assert batch.unchanged_failure_hold(reloaded, "tts", tmp_path)

    # Code repairs must release the old frozen-error hold.
    (tmp_path / "text_to_speech_v25.py").write_text("changed TTS", encoding="utf-8")
    assert not batch.unchanged_failure_hold(reloaded, "tts", tmp_path)
    (tmp_path / "text_to_speech_v25.py").write_text("text_to_speech_v25.py", encoding="utf-8")
    (tmp_path / "microgen_batch.py").write_text("updated runner", encoding="utf-8")
    assert not batch.unchanged_failure_hold(reloaded, "tts", tmp_path)


def test_transient_provider_or_unverified_failure_never_creates_permanent_hold(
        tmp_path, monkeypatch):
    import microgen_quality as quality
    for name in ("script_tts.json", "text_to_speech_v25.py", "microgen_batch.py"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    source_hash = quality.dependency_fingerprint(tmp_path, "tts")
    runner_hash = quality.sha256(tmp_path / "microgen_batch.py")
    for classification in ("TRANSIENT_EXHAUSTED", "UNVERIFIED_INPUTS", None):
        cp = {"last_error": {
            "stage": "tts",
            "recovery_disposition": classification,
            "input_fingerprint": source_hash,
            "recovery_runner_sha256": runner_hash,
        }}
        assert not batch.unchanged_failure_hold(cp, "tts", tmp_path)


def test_static_audio_fingerprint_is_immune_to_semantic_budget_changes(
        tmp_path, monkeypatch):
    import microgen_quality as quality
    (tmp_path / "script_tts.json").write_text("{}", encoding="utf-8")
    (tmp_path / "text_to_speech_v25.py").write_text("trusted entrypoint", encoding="utf-8")
    monkeypatch.setenv("MICROGEN_TIMED_CUES", "0")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    static_hash = quality.dependency_fingerprint(tmp_path, "tts")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "30")
    assert quality.dependency_fingerprint(tmp_path, "tts") == static_hash
    monkeypatch.setenv("MICROGEN_TIMED_CUES", "1")
    timed_hash = quality.dependency_fingerprint(tmp_path, "tts")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    assert quality.dependency_fingerprint(tmp_path, "tts") != timed_hash
