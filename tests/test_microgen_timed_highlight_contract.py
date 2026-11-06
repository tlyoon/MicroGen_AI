"""Offline regression for measured, source-bound highlights; no Gemini or ASR."""
from __future__ import annotations

import json
import tempfile
import wave
from pathlib import Path

import fitz
import pytest

from microgen_timed_highlight_contract import (
    MANIFEST, HighlightContractError, inspect_timed_highlights, _hash,
)


def _wav(path: Path, frames: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        out.writeframes(frames)


def stage(root: Path) -> Path:
    lecture = root / "isolated"
    lecture.mkdir()
    chunk_dir = lecture / "highlight_chunks"
    chunk_dir.mkdir()
    deck = fitz.open()
    rows = []
    for slide_no in (1, 2):
        page = deck.new_page(width=360, height=240)
        page.insert_text((35, 60), "Conservation of energy")
        page.insert_text((35, 90), "Energy transfers")
        single = fitz.open()
        target = single.new_page(width=360, height=240)
        target.insert_text((35, 60), "Conservation of energy")
        target.insert_text((35, 90), "Energy transfers")
        slide_file = lecture / f"slide{slide_no}.pdf"
        single.save(slide_file)
        single.close()

        one = b"\x04\x00" * 4800
        two = b"\x05\x00" * 6400
        _wav(lecture / f"slide{slide_no}.wav", one + two)
        cues = []
        for i, (fragment, label, y0, y1) in enumerate((
                (one, "Conservation of energy", 45, 65),
                (two, "Energy transfers", 75, 95)), 1):
            name = f"highlight_chunks/slide{slide_no}_cue{i}.wav"
            chunk_file = lecture / name
            _wav(chunk_file, fragment)
            cues.append({
                "element_id": f"s{slide_no}e{i}",
                "pdf_text": label,
                "pdf_bbox": [30, y0, 210, y1],
                "audio_chunk": name,
                "audio_chunk_sha256": _hash(chunk_file),
            })
        rows.append({
            "slide": slide_no,
            "slide_pdf_sha256": _hash(slide_file),
            "slide_wav_sha256": _hash(lecture / f"slide{slide_no}.wav"),
            "cues": cues,
        })
    deck.save(lecture / "slides.pdf")
    deck.close()
    (lecture / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text": "Conservation of energy. Energy transfers."},
                   {"slide": 2, "tts_text": "Conservation of energy. Energy transfers."}]
    }), encoding="utf8")
    (lecture / MANIFEST).write_text(json.dumps({
        "schema_version": 1,
        "timing_method": "measured_ordered_pcm_chunks",
        "slides_pdf_sha256": _hash(lecture / "slides.pdf"),
        "script_tts_sha256": _hash(lecture / "script_tts.json"),
        "slides": rows,
        "publication_allowed": False,
    }), encoding="utf8")
    return lecture


def _edit_manifest(lecture: Path, mutate) -> None:
    target = lecture / MANIFEST
    obj = json.loads(target.read_text(encoding="utf8"))
    mutate(obj)
    target.write_text(json.dumps(obj), encoding="utf8")


def test_real_pdf_text_and_exact_pcm_timing_verified() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        receipt = inspect_timed_highlights(lecture)
        assert receipt["slide_count"] == 2
        assert receipt["status"] == "SOURCE_AND_PCM_TIMING_STRUCTURALLY_VERIFIED"
        assert receipt["visual_highlight_rendering_verified"] is False
        assert receipt["spoken_word_to_element_alignment_verified"] is False
        assert receipt["publication_allowed"] is False
        cues = receipt["slides"][0]["elements"]
        assert len(cues) == 2
        assert cues[0]["start_seconds"] == 0.0
        assert cues[0]["end_seconds"] == 0.6
        assert cues[1]["start_seconds"] == 0.6
        assert cues[1]["end_seconds"] == 1.4


def test_tampered_wav_chunk_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        chunk = lecture / "highlight_chunks" / "slide1_cue1.wav"
        _wav(chunk, b"\x09\x00" * 4800)
        _edit_manifest(lecture, lambda x: x["slides"][0]["cues"][0].update({
            "audio_chunk_sha256": _hash(chunk)
        }))
        with pytest.raises(HighlightContractError, match="reconstruct WAV exactly"):
            inspect_timed_highlights(lecture)


def test_missing_or_misordered_element_cues_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        _edit_manifest(lecture, lambda x: x["slides"][0]["cues"].reverse())
        with pytest.raises(HighlightContractError, match="out-of-order PCM chunk"):
            inspect_timed_highlights(lecture)


def test_bad_pdf_text_mapping_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        _edit_manifest(lecture, lambda x: x["slides"][0]["cues"][0].update({
            "pdf_text": "A fabricated derivative absent from the source"
        }))
        with pytest.raises(HighlightContractError, match="PDF-text grounded"):
            inspect_timed_highlights(lecture)


def test_offpage_highlight_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        _edit_manifest(lecture, lambda x: x["slides"][0]["cues"][0].update({
            "pdf_bbox": [340, 20, 380, 60]
        }))
        with pytest.raises(HighlightContractError, match="Out-of-page"):
            inspect_timed_highlights(lecture)


def test_traversal_and_unsafe_chunk_names_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        _edit_manifest(lecture, lambda x: x["slides"][0]["cues"][0].update({
            "audio_chunk": "../secret.wav"
        }))
        with pytest.raises(HighlightContractError, match="Unsafe"):
            inspect_timed_highlights(lecture)


def test_audio_input_change_and_receipt_forgery_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        whole = lecture / "slide2.wav"
        _wav(whole, b"\x06\x00" * 11200)
        with pytest.raises(HighlightContractError, match="PDF/WAV hash changed"):
            inspect_timed_highlights(lecture)
        _edit_manifest(lecture, lambda x: x.update({"publication_allowed": True}))
        with pytest.raises(HighlightContractError, match="publication contract"):
            inspect_timed_highlights(lecture)


def test_absent_manifest_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lecture = stage(Path(tmp))
        (lecture / MANIFEST).unlink()
        with pytest.raises(HighlightContractError, match="Missing"):
            inspect_timed_highlights(lecture)
