"""Synthetic-only PR269 auto-discovery of external WAVs; no textbook or voice API."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from microgen_private_chapter_capture_discovery import (
    ChapterCaptureDiscoveryError, discover_chapter_wavs,
    make_private_declarations_template,
)
from microgen_private_chapter_audio_video import audit_chapter_captured_audio
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_private_chapter_audio_video import _fixture


def prepare(root: Path, *, copy_audio=True, labeled=True):
    chapter, filled_plan_path, original = _fixture(root)
    blank = json.loads(filled_plan_path.read_text(encoding="utf8"))
    drop = root/"external_wav_drop"
    drop.mkdir()
    for row in blank["sections"]:
        label = "section_" + row["section_id"].replace(".", "_")
        folder = drop/label
        folder.mkdir()
        if copy_audio:
            for wav in Path(row["audio_dir"]).glob("*.wav"):
                shutil.copy2(wav, folder/wav.name)
        row["audio_dir"] = None
        row["capture_manifest"] = None
    blank_file = root/"chapter_blank_plan.json"
    blank_file.write_text(json.dumps(blank), encoding="utf8")
    declares = make_private_declarations_template(chapter)
    if labeled:
        for row in declares["sections"]:
            row["declared_provider"] = "Externally supplied synthetic test"
            row["declared_voice"] = "Illustrative test sine only"
    labels = root/"voice_labels.json"
    labels.write_text(json.dumps(declares), encoding="utf8")
    return chapter, blank_file, drop, labels, original


def test_incomplete_chapter_reports_all_missing_files_once_no_partial_accepted_plan(tmp_path):
    chapter, blank, wav_root, labels, _ = prepare(tmp_path, copy_audio=False)
    target = tmp_path/"inventory_only"
    result = discover_chapter_wavs(
        chapter, blank, wav_root, target, declarations=labels)
    assert result["status"] == "PRIVATE_CHAPTER_CAPTURE_INVENTORY_INCOMPLETE_NOT_PUBLISHED"
    assert result["section_count"] == 2
    assert result["required_wav_count"] == 4
    assert result["missing_audio_files_total"] == 4
    assert result["sections_ready_for_import"] == 0
    assert result["complete_capture_plan_written"] is False
    assert all(row["missing_wav_files"] == ["slide01.wav", "slide02.wav"]
               for row in result["sections"])
    assert (target/"chapter_capture_discovery_receipt.json").is_file()
    assert not (target/"capture_plan_ready.json").exists()
    assert not (target/"capture_manifests").exists()


def test_complete_audio_but_no_provider_labels_does_not_forge_identity(tmp_path):
    chapter, blank, wav_root, _, _ = prepare(tmp_path, labeled=False)
    target = tmp_path/"still_awaiting_declaration"
    result = discover_chapter_wavs(chapter, blank, wav_root, target)
    assert result["structurally_usable_wav_count"] == 4
    assert result["missing_audio_files_total"] == 0
    assert not result["complete_capture_plan_written"]
    assert all(row["provider_and_voice_explicitly_declared"] is False
               for row in result["sections"])
    assert not (target/"capture_plan_ready.json").exists()


def test_complete_chapter_generates_all_wav_hashes_and_valid_pr268_plan(tmp_path):
    chapter, blank, wav_root, labels, original = prepare(tmp_path)
    before = [sha_file(Path(row["source_pdf"])) for row in original["cases"]]
    wav_before = [sha_file(p) for p in sorted(wav_root.rglob("*.wav"))]
    target = tmp_path/"completed_capture"
    result = discover_chapter_wavs(
        chapter, blank, wav_root, target, declarations=labels)
    assert result["status"] == "PRIVATE_CHAPTER_CAPTURE_MANIFESTS_READY_NOT_PUBLISHED"
    assert result["section_count"] == 2
    assert result["structurally_usable_wav_count"] == 4
    assert result["sections_ready_for_import"] == 2
    assert result["complete_capture_plan_written"] is True
    assert result["provider_identity_independently_verified"] is False
    assert result["narration_words_actually_spoken_verified"] is False
    assert result["provider_calls"] == 0
    assert result["local_language_model_invocations"] == 0
    assert result["publication_allowed"] is False
    plan = json.loads((target/"capture_plan_ready.json").read_text())
    assert all(Path(item["capture_manifest"]).is_file()
               for item in plan["sections"])
    assert [sha_file(Path(row["source_pdf"])) for row in original["cases"]] == before
    assert [sha_file(p) for p in sorted(wav_root.rglob("*.wav"))] == wav_before
    output = tmp_path/"verified_via_pr268"
    technical = audit_chapter_captured_audio(
        chapter, target/"capture_plan_ready.json", output)
    assert technical["slide_count"] == 4
    assert technical["section_count"] == 2
    assert technical["publication_allowed"] is False


def test_generated_capture_plan_can_render_two_private_section_videos(tmp_path):
    chapter, blank, wav_root, labels, _ = prepare(tmp_path)
    complete = tmp_path/"complete"
    discover_chapter_wavs(chapter, blank, wav_root, complete, declarations=labels)
    videos = tmp_path/"private_video_candidates"
    report = audit_chapter_captured_audio(
        chapter, complete/"capture_plan_ready.json", videos,
        render_private_videos=True)
    assert report["videos_created"] is True
    assert report["slide_count"] == 4
    assert report["publication_allowed"] is False
    assert len(list((videos/"section_videos").glob("*.mp4"))) == 2
    assert all(row["every_slide_midpoint_frame_verified"] is True
               for row in report["sections"])


@pytest.mark.parametrize("fault", [
    "missing_second_wav", "rogue_wav", "corrupted_wav",
    "uppercase_wav", "missing_directory",
])
def test_audio_inventory_anomalies_are_consolidated_no_complete_manifest(tmp_path, fault):
    chapter, blank, root, labels, _ = prepare(tmp_path)
    second = root/"section_1_2"
    if fault == "missing_second_wav":
        (second/"slide02.wav").unlink()
    elif fault == "rogue_wav":
        (second/"slide03.wav").write_bytes(b"bad")
    elif fault == "corrupted_wav":
        (second/"slide02.wav").write_bytes(b"invalid audio")
    elif fault == "uppercase_wav":
        (second/"slide02.wav").rename(second/"slide02.WAV")
    elif fault == "missing_directory":
        shutil.rmtree(second)
    target = tmp_path/"anomaly_inventory"
    result = discover_chapter_wavs(chapter, blank, root, target, declarations=labels)
    assert result["complete_capture_plan_written"] is False
    assert result["sections_ready_for_import"] == 1
    assert result["status"] == "PRIVATE_CHAPTER_CAPTURE_INVENTORY_INCOMPLETE_NOT_PUBLISHED"
    assert not (target/"capture_plan_ready.json").exists()


@pytest.mark.parametrize("fault", [
    "mutated_source", "reordered_labels", "forged_formal_flag",
    "missing_blank_plan_identity", "prior_output_exists",
])
def test_forged_source_labels_or_output_collision_fail_closed(tmp_path, fault):
    chapter, blank, root, labels, _ = prepare(tmp_path)
    target = tmp_path/"do_not_commit"
    if fault == "mutated_source":
        plan = json.loads(blank.read_text())
        with Path(plan["sections"][1]["source_pdf"]).open("ab") as f:
            f.write(b"forged chapter PDF suffix")
    elif fault == "reordered_labels":
        data = json.loads(labels.read_text())
        data["sections"].reverse()
        labels.write_text(json.dumps(data))
    elif fault == "forged_formal_flag":
        data = json.loads(labels.read_text())
        data["formal_voice_authorization_claimed"] = True
        labels.write_text(json.dumps(data))
    elif fault == "missing_blank_plan_identity":
        data = json.loads(blank.read_text())
        data["sections"][1]["capture_manifest"] = "already submitted"
        blank.write_text(json.dumps(data))
    elif fault == "prior_output_exists":
        target.mkdir()
        (target/"preserve.txt").write_text("keep")
    with pytest.raises((ChapterCaptureDiscoveryError, ValueError)):
        discover_chapter_wavs(chapter, blank, root, target, declarations=labels)
    assert not (target/"capture_plan_ready.json").exists()
    if fault == "prior_output_exists":
        assert (target/"preserve.txt").read_text() == "keep"


def test_wav_mutated_during_import_aborts_atomically(tmp_path, monkeypatch):
    import microgen_private_chapter_capture_discovery as discovery

    chapter, blank, root, labels, _ = prepare(tmp_path)
    original_audit = discovery.audit_portable_audio_import
    called = []
    def audit_then_tamper(*args, **kwargs):
        result = original_audit(*args, **kwargs)
        called.append(True)
        if len(called) == 1:
            with (root/"section_1_1"/"slide01.wav").open("ab") as f:
                f.write(b"tampered-after-first-section-audit")
        return result

    monkeypatch.setattr(discovery, "audit_portable_audio_import", audit_then_tamper)
    target = tmp_path/"nothing_committed"
    with pytest.raises(ChapterCaptureDiscoveryError, match="altered during scan"):
        discover_chapter_wavs(chapter, blank, root, target, declarations=labels)
    assert len(called) == 2
    assert not target.exists()
    assert not list(tmp_path.glob(".microgen-chapter-capture-*"))
