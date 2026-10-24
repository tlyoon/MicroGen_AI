"""Adversarial checks: never reuse speech clocks after source WAV replacement."""
import copy
import json
import struct
import wave

import pymupdf as fitz
import pytest

from microgen_audio_cue_binding import _verified_audio_rows, validate_audio_bound_cues
from microgen_corrected_cue_realign import (
    RealtimeCueError, regenerate_stage_cues,
)
from microgen_source_safe_orchestrator import (
    atomic_json, create_workspace, digest, read_json, source_bound_timeline,
    stage_existing_root_wavs,
)


def _wav(path, value=800, seconds=0.50):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack("<h", value) * int(seconds * 16000))


def _stage(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    with fitz.open() as pdf:
        for word in ("Remarkable", "Distinctive"):
            p = pdf.new_page(width=640, height=360)
            p.insert_text((50, 80), word, fontsize=22)
        pdf.save(original / "slides.pdf")
    (original / "script_tts.json").write_text(
        json.dumps({"slides": [
            {"slide": 1, "tts_text": "Remarkable"},
            {"slide": 2, "tts_text": "Distinctive"}
        ]}), encoding="utf-8")
    _wav(original / "slide1.wav")
    _wav(original / "slide2.wav", value=900)
    stage = tmp_path / "stage"
    create_workspace(original, stage)
    stage_existing_root_wavs(stage)
    source_bound_timeline(stage)
    source, rows, _ = _verified_audio_rows(stage)
    report = {
        "schema_version": 1,
        "status": "CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH",
        "source_pdf_sha256": source["source_pdf_sha256"],
        "narration_sha256": source["narration_sha256"],
        "stage_audio_bindings": rows,
        "results": [
            {"slide": i, "file": f"slide{i}.wav",
             "source_wav_sha256": rows[i-1]["wav_sha256"],
             "words": [{"word": token, "start": .1, "end": .25, "conf": .99}],
             "phonetic_identity_verified": False,
             "semantic_word_alignment_certified": False}
            for i, token in enumerate(("remarkable", "distinctive"), 1)],
        "phonetic_identity_verified": False,
        "semantic_alignment_verified": False,
        "publication_allowed": False,
    }
    manifest = tmp_path / "recognition.json"
    atomic_json(manifest, report)
    return stage, manifest, report


def test_current_recognition_yields_new_audio_bound_global_clocks(tmp_path):
    stage, report, _ = _stage(tmp_path)
    status = regenerate_stage_cues(stage, report)
    assert status["cue_count"] == 2
    assert status["publication_allowed"] is False
    doc = read_json(stage / "cues.json")
    assert doc["version"] == 2
    assert doc["elements"][1]["local_start"] == .1
    assert doc["elements"][1]["start_seconds"] == .6
    assert doc["spoken_word_alignment_verified"] is False
    assert doc["mathematics_semantics_verified"] is False
    assert validate_audio_bound_cues(stage, doc)["checked_cues"] == 2


def test_stale_old_asr_refused_after_legitimate_wav_replacement(tmp_path):
    stage, report_file, report = _stage(tmp_path)
    _wav(stage / "audio" / "slide1.wav", value=1100, seconds=.62)
    inv = read_json(stage / "audio_inventory.json")
    inv["entries"][0]["sha256"] = digest(stage / "audio" / "slide1.wav")
    atomic_json(stage / "audio_inventory.json", inv)
    source_bound_timeline(stage)
    with pytest.raises(RealtimeCueError, match="current WAV"):
        regenerate_stage_cues(stage, report_file)
    assert not (stage / "cues.json").exists()
    # A new *hypothetical* model observation now carries the replacement SHA.
    _, rows, _ = _verified_audio_rows(stage)
    newer = copy.deepcopy(report)
    newer["stage_audio_bindings"] = rows
    newer["results"][0]["source_wav_sha256"] = rows[0]["wav_sha256"]
    new_file = tmp_path / "new_observation.json"
    atomic_json(new_file, newer)
    status = regenerate_stage_cues(stage, new_file)
    assert status["cue_count"] == 2
    assert read_json(stage / "cues.json")["elements"][1]["start_seconds"] == .72


def test_legacy_asr_format_and_false_certification_rejected(tmp_path):
    stage, report_file, report = _stage(tmp_path)
    old = copy.deepcopy(report)
    old["status"] = "SOURCE_BOUND_OFFLINE_17_SLIDE_ASR"
    atomic_json(tmp_path / "old.json", old)
    with pytest.raises(RealtimeCueError):
        regenerate_stage_cues(stage, tmp_path / "old.json")
    forged = copy.deepcopy(report)
    forged["publication_allowed"] = True
    atomic_json(tmp_path / "fake.json", forged)
    with pytest.raises(RealtimeCueError):
        regenerate_stage_cues(stage, tmp_path / "fake.json")
    assert not (stage / "cues.json").exists()


def test_misordered_or_missing_slide_recognition_fails_closed(tmp_path):
    stage, _, report = _stage(tmp_path)
    bad = copy.deepcopy(report)
    bad["results"].reverse()
    atomic_json(tmp_path / "reversed.json", bad)
    with pytest.raises(RealtimeCueError, match="misordered"):
        regenerate_stage_cues(stage, tmp_path / "reversed.json")
    bad["results"] = bad["results"][:1]
    atomic_json(tmp_path / "missing.json", bad)
    with pytest.raises(RealtimeCueError, match="Missing"):
        regenerate_stage_cues(stage, tmp_path / "missing.json")
    assert not (stage / "cues.json").exists()


def test_asr_time_after_actual_audio_and_corrupt_confidence_rejected(tmp_path):
    stage, _, report = _stage(tmp_path)
    for name, item in (("time", {"start": .48, "end": .65, "conf": .99}),
                       ("conf", {"start": .1, "end": .2, "conf": 1.2})):
        bad = copy.deepcopy(report)
        bad["results"][0]["words"][0].update(item)
        path = tmp_path / f"{name}.json"
        atomic_json(path, bad)
        with pytest.raises(ValueError):
            regenerate_stage_cues(stage, path)
    assert not (stage / "cues.json").exists()


def test_existing_cues_are_never_replaced(tmp_path):
    stage, report_file, _ = _stage(tmp_path)
    regenerate_stage_cues(stage, report_file)
    previous = digest(stage / "cues.json")
    with pytest.raises(RealtimeCueError, match="overwritten"):
        regenerate_stage_cues(stage, report_file)
    assert digest(stage / "cues.json") == previous


def test_repeated_pdf_or_model_words_are_not_false_mathematical_alignment(tmp_path):
    stage, _, report = _stage(tmp_path)
    inconclusive = copy.deepcopy(report)
    inconclusive["results"][0]["words"].append(
        {"word": "remarkable", "start": .26, "end": .39, "conf": .99})
    path = tmp_path / "inconclusive.json"
    atomic_json(path, inconclusive)
    status = regenerate_stage_cues(stage, path)
    assert status["cue_count"] == 1
    assert status["mathematical_figure_alignment_verified"] is False


def test_offline_capture_checks_all_audio_again_after_last_recognition(tmp_path, monkeypatch):
    import sys
    import types
    import microgen_corrected_cue_realign as unit
    stage, _, _ = _stage(tmp_path)
    modeldir = tmp_path / "installed_vosk"
    (modeldir / "am").mkdir(parents=True)
    ffmpeg = tmp_path / "fake_ffmpeg"
    ffmpeg.write_bytes(b"unit-only executable marker")
    class FakeModel:
        def __init__(self, path):
            assert path == str(modeldir)
    monkeypatch.setitem(sys.modules, "vosk", types.SimpleNamespace(Model=FakeModel))
    names = {1: "remarkable", 2: "distinctive"}
    def fake_words(wav, model, ff):
        slide = int(wav.stem.replace("slide", ""))
        return {
            "source_wav_sha256": digest(wav),
            "words": [{"word": names[slide], "start": .1, "end": .25,
                       "conf": .99}],
            "phonetic_identity_verified": False,
            "semantic_word_alignment_certified": False,
        }
    monkeypatch.setattr(unit, "capture_offline_words", fake_words)
    output = tmp_path / "current_stage_asr.json"
    answer = unit.capture_current_audio_asr(stage, modeldir, ffmpeg, output)
    assert answer["slides"] == 2
    assert answer["publication_allowed"] is False
    assert regenerate_stage_cues(stage, output)["cue_count"] == 2
    assert read_json(output)["status"] == "CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH"


def test_capture_detects_mutation_of_earlier_audio_clip_and_refuses_report(
        tmp_path, monkeypatch):
    import sys
    import types
    import microgen_corrected_cue_realign as unit
    stage, _, _ = _stage(tmp_path)
    modeldir = tmp_path / "installed_vosk"
    (modeldir / "am").mkdir(parents=True)
    ffmpeg = tmp_path / "fake_ffmpeg"
    ffmpeg.write_bytes(b"local")
    monkeypatch.setitem(sys.modules, "vosk",
                        types.SimpleNamespace(Model=lambda path: object()))
    def fake_words(wav, model, ff):
        if wav.name == "slide2.wav":
            _wav(stage / "audio" / "slide1.wav", value=1700)
        return {
            "source_wav_sha256": digest(wav),
            "words": [],
            "phonetic_identity_verified": False,
            "semantic_word_alignment_certified": False,
        }
    monkeypatch.setattr(unit, "capture_offline_words", fake_words)
    output = tmp_path / "should_not_write.json"
    with pytest.raises(ValueError, match="SHA"):
        unit.capture_current_audio_asr(stage, modeldir, ffmpeg, output)
    assert not output.exists()
