"""Synthetic Chapter 1 private WAV intake and offline video candidate tests.

Sine tones ONLY: not narration, provider voices, original textbook material or AI.
"""
from __future__ import annotations

import array
import copy
import json
import math
from pathlib import Path
import wave

import pytest

from microgen_private_chapter_voice_campaign import audit_private_chapter_handoff
from microgen_private_chapter_audio_video import (
    PrivateChapterMediaError, audit_chapter_captured_audio, make_chapter_capture_plan,
)
from microgen_portable_audio_import import make_audio_capture_template
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_private_chapter_voice_campaign import make_chapter


def _make_audio(wav: Path, pitch: int):
    rate = 16000
    samples = array.array("h", [
        int(4200 * math.sin(2 * math.pi * pitch * i / rate))
        for i in range(rate * 2)
    ])
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(samples.tobytes())


def _fixture(root: Path):
    original = make_chapter(root)
    prepared = root / "chapter_bundle"
    report = audit_private_chapter_handoff(original, prepared)
    assert report["section_count"] == 2
    private_original_manifest = root / "chapter_source_manifest.json"
    private_original_manifest.write_text(json.dumps(original), encoding="utf8")
    plan = make_chapter_capture_plan(prepared, private_original_manifest)
    assert all(x["audio_dir"] is None for x in plan["sections"])
    assert all(x["capture_manifest"] is None for x in plan["sections"])
    for section_row in plan["sections"]:
        section = section_row["section_id"]
        name = "section_" + section.replace(".", "_")
        handoff = prepared / "voice_inputs" / (name + ".json")
        capture = make_audio_capture_template(handoff)
        capture["declared_provider"] = "External illustrative test input"
        capture["declared_voice"] = "Synthetic waveform only"
        audio = root / ("audio_" + name)
        audio.mkdir()
        for index, wav_row in enumerate(capture["captured_wavs"], 1):
            wav = audio / wav_row["filename"]
            _make_audio(wav, 260 + index * 37)
            wav_row["wav_sha256"] = sha_file(wav)
        manifest = root / (name + "_capture.json")
        manifest.write_text(json.dumps(capture), encoding="utf8")
        section_row["audio_dir"] = str(audio)
        section_row["capture_manifest"] = str(manifest)
    capture_plan = root / "capture_plan.json"
    capture_plan.write_text(json.dumps(plan), encoding="utf8")
    return prepared, capture_plan, original


def test_real_synthetic_full_chapter_audio_intake_is_atomic_and_not_publication(tmp_path):
    chapter, plan, original = _fixture(tmp_path)
    sources_before = [sha_file(Path(c["source_pdf"])) for c in original["cases"]]
    output = tmp_path / "chapter_verified"
    result = audit_chapter_captured_audio(chapter, plan, output)
    assert result["status"] == "PRIVATE_CHAPTER_EXTERNAL_WAV_INTAKE_VERIFIED_NOT_PUBLISHED"
    assert result["section_count"] == 2
    assert result["slide_count"] == 4
    assert result["videos_created"] is False
    assert result["external_wavs_technically_verified"] is True
    assert result["publication_allowed"] is False
    assert result["cloud_provider_calls"] == 0
    assert result["local_language_model_invocations"] == 0
    assert all(not r["narration_words_actually_spoken_verified"] for r in result["sections"])
    assert (output / "chapter_private_audio_video_receipt.json").exists()
    assert [sha_file(Path(c["source_pdf"])) for c in original["cases"]] == sources_before


@pytest.mark.parametrize("fault", [
    "missing_audio_path", "tampered_wav", "wrong_manifest_text_sha",
    "wrong_source_slides", "changed_original_source", "reordered_section",
    "forged_formal_approval",
    "existing_destination",
])
def test_bad_capture_member_fails_whole_chapter_without_partial_receipt(tmp_path, fault):
    chapter, plan_path, _ = _fixture(tmp_path)
    plan = json.loads(plan_path.read_text())
    output = tmp_path / "chapter_should_not_commit"
    if fault == "missing_audio_path":
        plan["sections"][1]["audio_dir"] = None
    elif fault == "tampered_wav":
        audio = Path(plan["sections"][1]["audio_dir"])
        with (audio / "slide02.wav").open("ab") as f:
            f.write(b"unauthorized")
    elif fault == "wrong_manifest_text_sha":
        manifest = Path(plan["sections"][1]["capture_manifest"])
        capture = json.loads(manifest.read_text())
        capture["captured_wavs"][0]["source_text_sha256"] = "0" * 64
        manifest.write_text(json.dumps(capture))
    elif fault == "wrong_source_slides":
        plan["sections"][1]["slides_dir"] = plan["sections"][0]["slides_dir"]
    elif fault == "changed_original_source":
        source = Path(plan["sections"][1]["source_pdf"])
        with source.open("ab") as f:
            f.write(b"changed-after-chapter-readiness")
    elif fault == "reordered_section":
        plan["sections"].reverse()
    elif fault == "forged_formal_approval":
        plan["formal_voice_authorization_claimed"] = True
    elif fault == "existing_destination":
        output.mkdir()
        (output / "preserve.txt").write_text("keep")
    plan_path.write_text(json.dumps(plan))
    with pytest.raises((PrivateChapterMediaError, ValueError)):
        audit_chapter_captured_audio(chapter, plan_path, output)
    assert not (output / "chapter_private_audio_video_receipt.json").exists()
    if fault == "existing_destination":
        assert (output / "preserve.txt").read_text() == "keep"


def test_private_two_section_ffmpeg_video_candidates_match_all_source_frames(tmp_path):
    chapter, plan, _ = _fixture(tmp_path)
    output = tmp_path / "chapter_video_bundle"
    result = audit_chapter_captured_audio(
        chapter, plan, output, render_private_videos=True)
    assert result["section_count"] == 2
    assert result["slide_count"] == 4
    assert result["videos_created"]
    assert result["publication_allowed"] is False
    for item in result["sections"]:
        assert item["every_slide_midpoint_frame_verified"] is True
        mp4 = output / item["private_video_file"]
        assert mp4.is_file()
        assert sha_file(mp4) == item["private_video_sha256"]
        assert item["private_video_seconds"] > 0
    assert len(list((output / "section_videos").glob("*.mp4"))) == 2


def test_failed_second_section_render_discards_all_provisional_videos(tmp_path, monkeypatch):
    import microgen_private_chapter_audio_video as chapter_av

    chapter, plan, _ = _fixture(tmp_path)
    called = []
    def render_then_fail(slides, narration, audio, destination, **kwargs):
        called.append(str(slides))
        if len(called) == 2:
            raise RuntimeError("synthetic second-section FFmpeg failure")
        destination.mkdir()
        (destination / "lecture_diagnostic_only.mp4").write_bytes(b"provisional")
        from microgen_pronunciation_closed_loop import sha_file
        return {
            "status": "DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION",
            "slide_count": 2,
            "all_slide_midpoints_source_pixel_checked": True,
            "publication_allowed": False,
            "formal_voice_authorized": False,
            "rendered_pdf_sha256": sha_file(slides / "slides_teaching_candidate.pdf"),
            "video_slide_frame_alignment": [{}, {}],
            "diagnostic_mp4_duration_seconds": 4.0,
        }

    monkeypatch.setattr(chapter_av, "build_demo_video", render_then_fail)
    target = tmp_path / "whole_chapter_uncommitted"
    with pytest.raises(RuntimeError, match="second-section"):
        audit_chapter_captured_audio(chapter, plan, target, render_private_videos=True)
    assert len(called) == 2
    assert not target.exists()
    assert not list(tmp_path.glob(".microgen-chapter-av-*"))
