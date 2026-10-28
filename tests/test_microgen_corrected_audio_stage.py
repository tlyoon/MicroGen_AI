"""Source/clip integrity regression for isolated corrected Section 2.5 staging."""
import copy
import json
import struct
import wave

import pymupdf as fitz
import pytest

import microgen_corrected_audio_stage as unit
from microgen_audio_cue_binding import _verified_audio_rows
from microgen_source_safe_orchestrator import (
    atomic_json, create_workspace, digest, read_json, verify_workspace,
)


def _wav(path, level=800, seconds=.20):
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(16000)
        sound.writeframes(struct.pack("<h", level) * round(seconds * 16000))


def _fixture(tmp_path):
    source = tmp_path / "SOURCE"
    source.mkdir()
    with fitz.open() as pdf:
        for i in range(1, 18):
            page = pdf.new_page(width=640, height=360)
            page.insert_text((25, 45), f"Source slide {i}")
        pdf.save(source / "slides.pdf")
    (source / "script_tts.json").write_text(
        json.dumps({"slides": [
            {"slide": i, "tts_text": f"Source slide number {i}"}
            for i in range(1, 18)]}), encoding="utf8")
    (source / "slides.mp4").write_bytes(b"isolated synthetic MP4 identity fixture")
    original = tmp_path / "LEGACY_RECOVERY"
    create_workspace(source, original)
    (original / "audio").mkdir()
    references = []
    for i in range(1, 18):
        file = original / "audio" / f"slide{i}.wav"
        _wav(file, level=800 + i)
        references.append({"slide": i, "sha256": digest(file)})
    mp4sha = digest(source / "slides.mp4")
    atomic_json(original / "legacy_mp4_audio_receipt.json", {
        "status": "PROVISIONAL_NOT_PUBLISHABLE",
        "scene_evidence": {"mp4_sha256": mp4sha},
        "clips": references,
    })
    (original / "cues.json").write_text('{"old":"stale"}')
    chosen = tmp_path / "SELECTION"
    chosen.mkdir()
    trials = []
    for i, risk in ((5, "CDOT"), (6, "CDOT"), (10, "Y_VALUE")):
        f = chosen / f"slide{i:02d}_{risk}_UNAPPROVED.wav"
        _wav(f, level=1200 + i, seconds=.31)
        trials.append({
            "slide": i, "risk": risk, "wav_sha256": digest(f),
            "trial_path": str(f), "phonetic_approved": False,
            "voice_independently_verified": False,
        })
    src = verify_workspace(original)
    receipt = {
        "schema_version": 1, "status": "SHADOW_ONLY_TRIAL_SELECTION",
        "source_pdf_sha256": src["source_pdf_sha256"],
        "source_narration_sha256": src["narration_sha256"],
        "source_mp4_sha256": mp4sha, "trials": trials,
        "publication_allowed": False, "original_audio_modified": False,
    }
    atomic_json(chosen / "selection_receipt.json", receipt)
    return source, original, chosen, receipt


def test_17_source_verified_clips_make_isolated_corrected_stage_without_old_cues(tmp_path):
    src, old, chosen, _ = _fixture(tmp_path)
    dest = tmp_path / "newstage"
    result = unit.prepare_section25_corrected_wavs(old, chosen, dest)
    assert result["slides"] == 17
    assert result["corrected_slides"] == [5, 6, 10]
    assert result["old_cues_copied"] is False
    assert result["publication_allowed"] is False
    assert not (dest / "cues.json").exists()
    assert (old / "cues.json").read_text() == '{"old":"stale"}'
    source, rows, intervals = _verified_audio_rows(dest)
    assert len(rows) == 17
    assert intervals[5]["start_seconds"] == pytest.approx(1.11)
    assert rows[4]["wav_sha256"] == digest(chosen / "slide05_CDOT_UNAPPROVED.wav")
    assert rows[6]["wav_sha256"] == digest(old / "audio" / "slide7.wav")
    assert read_json(dest / "corrected_stage_receipt.json")[
        "fresh_offline_recognition_required"] is True
    assert (src / "slides.mp4").read_bytes() == b"isolated synthetic MP4 identity fixture"
    assert not (src / "slide5.wav").exists()
    assert source["slide_count"] == 17


def test_modified_trial_wav_is_rejected_before_any_stage_write(tmp_path):
    _source, old, selection, _ = _fixture(tmp_path)
    _wav(selection / "slide06_CDOT_UNAPPROVED.wav", level=901)
    target = tmp_path / "rejected"
    with pytest.raises(unit.CorrectedStageError, match="changed"):
        unit.prepare_section25_corrected_wavs(old, selection, target)
    assert not target.exists()


def test_mutated_legacy_audio_is_rejected_before_stage_write(tmp_path):
    _source, old, selection, _ = _fixture(tmp_path)
    _wav(old / "audio" / "slide7.wav", level=911)
    target = tmp_path / "rejected"
    with pytest.raises(unit.CorrectedStageError, match="changed"):
        unit.prepare_section25_corrected_wavs(old, selection, target)
    assert not target.exists()


@pytest.mark.parametrize("tamper", ["missing", "duplicate", "false_approval", "wrong_source"])
def test_bad_selection_never_creates_a_stage(tmp_path, tamper):
    _source, old, selected, report = _fixture(tmp_path)
    changed = copy.deepcopy(report)
    if tamper == "missing":
        changed["trials"].pop()
    elif tamper == "duplicate":
        changed["trials"][0] = copy.deepcopy(changed["trials"][1])
    elif tamper == "false_approval":
        changed["trials"][0]["phonetic_approved"] = True
    else:
        changed["source_pdf_sha256"] = "f" * 64
    atomic_json(selected / "selection_receipt.json", changed)
    target = tmp_path / "rejected"
    with pytest.raises(unit.CorrectedStageError):
        unit.prepare_section25_corrected_wavs(old, selected, target)
    assert not target.exists()


def test_refuses_to_overwrite_and_stage_inside_protected_folders(tmp_path):
    source, old, selection, _ = _fixture(tmp_path)
    for destination in (source / "new", old / "new", selection / "new", tmp_path):
        with pytest.raises(unit.CorrectedStageError):
            unit.prepare_section25_corrected_wavs(old, selection, destination)


def test_duration_over_strict_ten_minute_bound_fails_before_writes(tmp_path, monkeypatch):
    _source, old, selection, _ = _fixture(tmp_path)
    monkeypatch.setattr(unit, "_duration", lambda wav: 40.0)
    dest = tmp_path / "too_long"
    with pytest.raises(unit.CorrectedStageError, match="600"):
        unit.prepare_section25_corrected_wavs(old, selection, dest)
    assert not dest.exists()


def test_mutating_source_during_copy_cleans_only_the_new_stage(tmp_path, monkeypatch):
    _source, old, selection, _ = _fixture(tmp_path)
    original_copy = unit.shutil.copyfile
    def interrupted_copy(src, dst):
        original_copy(src, dst)
        if str(src).endswith("slide7.wav"):
            # Simulate a different owner mutating an input during staging.
            _wav(src, level=555)
    monkeypatch.setattr(unit.shutil, "copyfile", interrupted_copy)
    new = tmp_path / "interrupted_stage"
    with pytest.raises(unit.CorrectedStageError, match="changed"):
        unit.prepare_section25_corrected_wavs(old, selection, new)
    assert not new.exists()
    assert (old / "audio" / "slide7.wav").is_file()


def test_preflight_requires_original_video_identity(tmp_path):
    source, old, selected, _ = _fixture(tmp_path)
    (source / "slides.mp4").write_bytes(b"changed historical media")
    new = tmp_path / "badsource"
    with pytest.raises(unit.CorrectedStageError, match="Source MP4"):
        unit.prepare_section25_corrected_wavs(old, selected, new)
    assert not new.exists()


def test_selection_receipt_changed_during_copy_cannot_authenticate_stage(
        tmp_path, monkeypatch):
    _source, old, selection, _ = _fixture(tmp_path)
    original_copy = unit.shutil.copyfile
    touched = [False]
    def rewrite_selection(src, dst):
        original_copy(src, dst)
        if not touched[0]:
            touched[0] = True
            path = selection / "selection_receipt.json"
            record = read_json(path)
            record["source_revision_note"] = "modified mid-copy"
            atomic_json(path, record)
    monkeypatch.setattr(unit.shutil, "copyfile", rewrite_selection)
    target = tmp_path / "untrustworthy_receipt"
    with pytest.raises(unit.CorrectedStageError, match="Source changed"):
        unit.prepare_section25_corrected_wavs(old, selection, target)
    assert not target.exists()
