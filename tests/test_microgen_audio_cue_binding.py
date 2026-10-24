"""Regression for the defect: corrected audio could reuse stale ASR/PDF cue times."""
import copy
import json
import struct
import wave

import pymupdf as fitz
import pytest

from microgen_source_safe_orchestrator import (
    create_workspace, stage_existing_root_wavs, source_bound_timeline,
    read_json, atomic_json, digest, render_complete_staged_lesson,
)
from microgen_audio_cue_binding import (
    AudioCueBindingError, bind_cues_to_current_audio,
    validate_audio_bound_cues,
)


def _write_wav(path, duration=.4, magnitude=1000):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(struct.pack("<h", magnitude)*round(duration*16000))


def _stage(tmp_path):
    lesson = tmp_path/"original"
    lesson.mkdir()
    with fitz.open() as pages:
        for _ in range(2):
            page = pages.new_page(width=640, height=360)
            page.insert_text((35, 60), "Unique mathematical limit", fontsize=16)
        pages.save(lesson/"slides.pdf")
    (lesson/"script_tts.json").write_text(
        json.dumps({"slides":[{"slide":1,"tts_text":"The limit."},
                              {"slide":2,"tts_text":"The limit."}]}),
        encoding="utf8"
    )
    _write_wav(lesson/"slide1.wav")
    _write_wav(lesson/"slide2.wav")
    stage=tmp_path/"stage"
    create_workspace(lesson,stage)
    stage_existing_root_wavs(stage)
    source_bound_timeline(stage)
    with fitz.open(lesson/"slides.pdf") as pages:
        box=list(pages[1].get_text("words")[0][:4])
    cue={"slide":2,"box":box,"text":"Unique",
         "local_start":.1,"local_end":.25,
         "start_seconds":.5,"end_seconds":.65}
    return lesson,stage,cue


def test_bound_audio_and_word_geometry_pass(tmp_path):
    _source,stage,cue=_stage(tmp_path)
    evidence=bind_cues_to_current_audio(stage,[cue])
    assert evidence["version"]==2
    result=validate_audio_bound_cues(stage,evidence)
    assert result["checked_audio_slides"]==2
    assert result["checked_cues"]==1
    assert result["publication_allowed"] is False


def test_stale_timing_manifest_rejected_even_after_legitimate_audio_restage(tmp_path):
    _source,stage,cue=_stage(tmp_path)
    stale=bind_cues_to_current_audio(stage,[cue])
    _write_wav(stage/"audio"/"slide2.wav",duration=.5,magnitude=1500)
    inv=read_json(stage/"audio_inventory.json")
    inv["entries"][1]["sha256"]=digest(stage/"audio"/"slide2.wav")
    atomic_json(stage/"audio_inventory.json",inv)
    # This is exactly what a proper replacement does: it updates its SHA
    # and measured timeline. Previously v1 cues were silently reusable.
    source_bound_timeline(stage)
    with pytest.raises(AudioCueBindingError,match="Unbound or stale"):
        validate_audio_bound_cues(stage,stale)


def test_corrupted_audio_rejected_without_trusting_receipts(tmp_path):
    _source,stage,cue=_stage(tmp_path)
    manifest=bind_cues_to_current_audio(stage,[cue])
    _write_wav(stage/"audio"/"slide2.wav",duration=.4,magnitude=1700)
    with pytest.raises(AudioCueBindingError,match="SHA"):
        validate_audio_bound_cues(stage,manifest)


def test_v1_manifest_and_moved_cues_fail_before_renderer_makes_output(tmp_path):
    _source,stage,cue=_stage(tmp_path)
    bound=bind_cues_to_current_audio(stage,[cue])
    old={"version":1,"elements":[cue]}
    with pytest.raises(AudioCueBindingError):
        validate_audio_bound_cues(stage,old)
    atomic_json(stage/"cues.json",old)
    with pytest.raises(AudioCueBindingError):
        render_complete_staged_lesson(stage,ffmpeg=None)
    assert not (stage/"rendered").exists()
    assert not (stage/"page_pdf").exists()
    moved=copy.deepcopy(bound)
    moved["elements"][0]["local_start"]+=.11
    with pytest.raises(AudioCueBindingError,match="clock"):
        validate_audio_bound_cues(stage,moved)


def test_wrong_source_box_is_rejected(tmp_path):
    _source,stage,cue=_stage(tmp_path)
    bound=bind_cues_to_current_audio(stage,[cue])
    invalid=copy.deepcopy(bound)
    invalid["elements"][0]["box"]=[1,1,999,999]
    with pytest.raises(AudioCueBindingError,match="geometry"):
        validate_audio_bound_cues(stage,invalid)
