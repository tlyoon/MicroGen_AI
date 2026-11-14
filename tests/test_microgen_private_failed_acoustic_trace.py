"""Failed independent acoustic replies are retained only in private HP scratch.

No provider calls, no publication approvals and no local speech models.
"""
import hashlib
import json
import socket
from pathlib import Path

import pytest

import microgen_private_acoustic_trace as trace
from microgen_tts_acoustic_qa import _input_snapshot


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(tmp_path, monkeypatch):
    local = tmp_path / "Local"
    work = local / "MicroGen_AI_Checkpoints" / "BOUNDED_G2"
    stage = work / "2.5"
    stage.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(socket, "gethostname", lambda: "hp")
    (work / ".microgen_bounded_provider_authorization.json").write_text(
        '{"schema_version":1,"publication_authorized":false}', encoding="utf8")
    (stage / ".microgen_tts_provenance.json").write_bytes(b'{"voice":"Kore"}')
    (stage / "script_tts.json").write_bytes(b'{"slides":[1,2]}')
    texts = ["The first original speech", "The second original speech"]
    for i in (1, 2):
        (stage / f"slide{i}.wav").write_bytes(b"FAKE-WAV-" + bytes([i]))
    snap = _input_snapshot(stage, len(texts))
    report = {
        "review_required_slides": [2],
        "input_snapshot_sha256": snap,
        "slides": [
            {"slide": i, "audio_sha256": snap[f"slide{i}.wav"],
             "expected_spoken_sha256": _sha(text.encode("utf8")),
             "assessment": "REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE" if i == 2
                           else "ASR_SCREEN_PASS_LISTENING_REQUIRED",
             "source_pronunciation_risks": [],
             "transcripts": [text, text.replace("original", "possibly unusual")]}
            for i, text in enumerate(texts, 1)
        ],
    }
    return stage, texts, report


def test_failed_real_review_preserved_locally_with_full_blind_evidence(tmp_path, monkeypatch):
    stage, texts, report = fixture(tmp_path, monkeypatch)
    models = ("gemini-3.5-flash", "gemini-3.8-flash")
    assert trace.retain_private_failed_acoustic_review(stage, texts, report, models)
    saved = list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    assert len(saved) == 1
    payload = json.loads(saved[0].read_text())
    assert payload["status"] == "PRIVATE_FAILED_ASR_EVIDENCE_NOT_ACCEPTED"
    assert payload["slides"][1]["original_blind_transcripts"] == (
        report["slides"][1]["transcripts"])
    assert payload["accepted_for_video"] is False
    assert payload["publication_allowed"] is False
    assert payload["phonetic_accuracy_certified"] is False
    assert trace.retain_private_failed_acoustic_review(
        stage, texts, report, models)
    assert len(list(stage.glob(".microgen_private_acoustic_failed_*.json"))) == 1


@pytest.mark.parametrize("mutation", ["host", "auth", "wav", "snapshot", "model", "text"])
def test_unsafe_or_changed_source_evidence_cannot_be_saved(
    tmp_path, monkeypatch, mutation,
):
    stage, texts, report = fixture(tmp_path, monkeypatch)
    models = ("gemini-3.5-flash", "gemini-3.8-flash")
    if mutation == "host":
        monkeypatch.setattr(socket, "gethostname", lambda: "Dell-115")
    elif mutation == "auth":
        (stage.parent / ".microgen_bounded_provider_authorization.json").unlink()
    elif mutation == "wav":
        (stage / "slide1.wav").write_bytes(b"CHANGED")
    elif mutation == "snapshot":
        report["input_snapshot_sha256"] = {}
    elif mutation == "model":
        models = ("gemini-3.5-flash", "gemini-3.5-flash")
    else:
        texts[0] = "different text"
    assert not trace.retain_private_failed_acoustic_review(
        stage, texts, report, models)
    assert not list(stage.glob(".microgen_private_acoustic_failed_*.json"))


def test_oversized_or_forged_transcripts_not_retained(tmp_path, monkeypatch):
    stage, texts, report = fixture(tmp_path, monkeypatch)
    report["slides"][0]["transcripts"][0] = "A" * 15000
    assert not trace.retain_private_failed_acoustic_review(
        stage, texts, report, ("gemini-3.5-flash", "gemini-3.8-flash"))


def test_no_failed_review_means_no_extra_private_capture(tmp_path, monkeypatch):
    stage, texts, report = fixture(tmp_path, monkeypatch)
    report["review_required_slides"] = []
    assert not trace.retain_private_failed_acoustic_review(
        stage, texts, report, ("gemini-3.5-flash", "gemini-3.8-flash"))
