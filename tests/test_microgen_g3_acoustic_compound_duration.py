"""Source-independent G3 two-reviewer lexical QA + bounded TTS pacing repair.

These tests do not attempt independent acoustic recognition. Severe PCM
duration is only a triage signal. Original source, voice and user records
must remain intact, genuine changed math or invented passage fails closed.
"""
import io
import json
import wave

import pytest

from microgen_flash_tts import (
    FlashTTSError, render_batch, severe_duration_outlier,
)
from microgen_tts_acoustic_qa import mismatch_details


def pcm_wav(seconds: float) -> bytes:
    memory=io.BytesIO()
    with wave.open(memory,"wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0"*round(24000*seconds))
    return memory.getvalue()


@pytest.mark.parametrize("written,heard",[
    ("roadmap", "road map"),
    ("anti-parallel", "antiparallel"),
    ("antiparallel", "anti parallel"),
    ("nonzero acceleration", "non zero acceleration"),
    ("non-zero acceleration", "non 0 acceleration"),
    ("velocity is nonzero", "velocity is nonzero"),
])
def test_same_spoken_compound_is_asr_orthography_not_defect(written,heard):
    row=mismatch_details(written,heard)
    assert row["difference_fraction_upper_bound"] == 0
    assert row["sensitive_mismatches"] == 0


@pytest.mark.parametrize("expected,heard",[
    ("acceleration is nonzero", "acceleration is zero"),
    ("acceleration is zero", "acceleration is nonzero"),
    ("motion is antiparallel", "motion is parallel"),
    ("constant is 40", "constant is 50"),
    ("the number is nonzero", "the number is negative"),
    ("the velocity is not zero", "the velocity is zero"),
])
def test_negative_or_changed_physics_still_acoustically_blocked(expected,heard):
    diff=mismatch_details(expected,heard)
    assert diff["sensitive_mismatches"]>0 or diff["difference_fraction_upper_bound"]>0.05


SOURCE=" ".join(f"word{i}" for i in range(1,39))


def test_real_style_38_words_50_seconds_is_severely_overlong():
    assert severe_duration_outlier(SOURCE,50.04)
    assert not severe_duration_outlier(SOURCE,20.1)
    assert not severe_duration_outlier("short explanation",50.0)
    assert not severe_duration_outlier(SOURCE,35.0)


def test_same_model_same_voice_retry_before_any_audio_installed(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","2")
    seen=[]
    def source_renderer(text,spec):
        seen.append((spec["provider"],spec["model"],spec["voice"]))
        return pcm_wav(50 if len(seen)==1 else 23)
    stage=tmp_path/"output"
    report=render_batch([SOURCE],stage,speak=source_renderer)
    assert len(seen)==2
    assert seen[0]==seen[1]
    assert report["engine"]=="gemini_flash_lite_tts"
    assert report["slides"][0]["bounded_duration_recovery_attempts"]==1
    assert report["slides"][0]["severe_duration_screen_passed"] is True
    assert stage.joinpath("slide01.wav").is_file()
    assert stage.joinpath("private_flash_tts_batch_receipt.json").is_file()


def test_grossly_overlong_speech_exhausts_finite_engines_without_publication(
        tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","2")
    calls=[]
    def always_untrustworthy(text,spec):
        calls.append(spec["provider"])
        return pcm_wav(50)
    stage=tmp_path/"output"
    with pytest.raises(FlashTTSError,match="TTS batch failed all authorized"):
        render_batch([SOURCE],stage,speak=always_untrustworthy)
    assert len(calls)==4
    assert calls.count("gemini_flash_lite_tts")==2
    assert calls.count("gemini_flash_tts")==2
    assert not stage.exists()
    assert not any(tmp_path.glob(".microgen-flash-batch-*"))


def test_ordinary_short_and_long_source_pauses_not_failed():
    assert not severe_duration_outlier("The answer is two.",8.0)
    assert not severe_duration_outlier(SOURCE,38.0)
    assert severe_duration_outlier(SOURCE,45.0)


def test_invented_additional_spoken_passage_remains_a_material_error():
    expected="A leftward-moving particle may have positive acceleration."
    heard=(expected+" Therefore the particle definitely moves west "
           "and its final acceleration is plus 999 meters per second squared.")
    diff=mismatch_details(expected,heard)
    assert diff["difference_fraction_upper_bound"]>0.05
    assert diff["sensitive_mismatches"]>0


@pytest.mark.skipif(
    not __import__("os").environ.get("MICROGEN_REAL_G3_SECTION26_STAGE"),
    reason="Opt-in original source/WAV evidence on authorized HP",
)
def test_authentic_g3_dual_gemini_trace_and_46_cue_duration_evidence():
    import os
    import hashlib
    from pathlib import Path
    from text_to_speech_v25 import normalize_scientific_speech
    stage=Path(os.environ["MICROGEN_REAL_G3_SECTION26_STAGE"])
    assert hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest()==(
        "5b6c6d6750e6b0ce8b693c5da361ac9f973480ecfa55e6a6097194820fc6a032"
    )
    traces=list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    assert len(traces)==1
    original=traces[0].read_bytes()
    assert hashlib.sha256(original).hexdigest()[:20] in traces[0].name
    review=json.loads(original)
    assert review["models"]==["gemini-3.5-flash","gemini-3.8-flash"]
    slides=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))["slides"]
    assert len(slides)==len(review["slides"])==13
    assert review["review_required_slides"]==[2,11,13]
    for n in (2,11):
        expected=normalize_scientific_speech(slides[n-1]["tts_text"])
        heard=review["slides"][n-1]["original_blind_transcripts"]
        assert len(heard)==2
        for recognizer in heard:
            compared=mismatch_details(expected,recognizer)
            assert compared["difference_fraction_upper_bound"]==0
            assert compared["sensitive_mismatches"]==0
    expected=normalize_scientific_speech(slides[12]["tts_text"])
    for recognizer in review["slides"][12]["original_blind_transcripts"]:
        assert mismatch_details(
            expected,recognizer)["difference_fraction_upper_bound"]>0.9
    cue_plan=json.loads((stage/".microgen_timed_cue_plan.json").read_text(
        encoding="utf8"))
    anomaly=[];count=0
    for slide in cue_plan["slides"]:
        for n,cue in enumerate(slide["cues"],1):
            count+=1
            with wave.open(str(stage/"highlight_chunks"/
                               f"slide{slide['slide']}_cue{n}.wav"),"rb") as wav:
                seconds=wav.getnframes()/wav.getframerate()
            if severe_duration_outlier(cue["spoken_text"],seconds):
                anomaly.append((slide["slide"],n))
    assert count==46
    assert anomaly==[(13,2)]
