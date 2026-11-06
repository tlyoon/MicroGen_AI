"""Deterministic offline tests for one-engine, atomic measured Gemini cue synthesis."""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import fitz
import pytest

from microgen_timed_cue_tts import (
    PLAN_FILE, CueTTSError,produce_measured_cue_audio,
)
from microgen_timed_cue_planner import sha
from microgen_timed_highlight_contract import (
    MANIFEST, inspect_timed_highlights,
)
from microgen_tts_provenance import verify_manifest
from text_to_speech_v25 import normalize_scientific_speech


def input_stage(root: Path) -> Path:
    stage=root/"isolated"
    stage.mkdir()
    pdf=fitz.open()
    rows=[]
    for i in (1,2):
        pdf.new_page(width=360,height=240).insert_text(
            (40,65),"Conservation of momentum and energy")
        pdf[-1].insert_text((40,95),"Transport of radiation and momentum")
    pdf.save(stage/"slides.pdf")
    for i in (1,2):
        one=fitz.open()
        one.insert_pdf(pdf,from_page=i-1,to_page=i-1)
        one.save(stage/f"slide{i}.pdf")
        one.close()
        rows.append({
            "slide":i,
            "slide_pdf_sha256":sha(stage/f"slide{i}.pdf"),
            "cues":[
                {"element_id":f"s{i}e1",
                 "pdf_text":"Conservation of momentum and energy",
                 "spoken_text":"Conservation of momentum and energy.",
                 "pdf_bbox":[35,50,300,72]},
                {"element_id":f"s{i}e2",
                 "pdf_text":"Transport of radiation and momentum",
                 "spoken_text":"Transport of radiation and momentum.",
                 "pdf_bbox":[35,80,300,102]},
            ]})
    pdf.close()
    (stage/"script_tts.json").write_text(json.dumps({
        "slides":[{
            "slide":i,
            "tts_text":"Conservation of momentum and energy. "
                       "Transport of radiation and momentum.",
            "narration":"Conservation of momentum and energy. "
                        "Transport of radiation and momentum.",
        } for i in (1,2)]
    }),encoding="utf8")
    (stage/PLAN_FILE).write_text(json.dumps({
        "schema_version":1,
        "planning_method":"source_pdf_overlap_conservative",
        "slides_pdf_sha256":sha(stage/"slides.pdf"),
        "script_tts_sha256":sha(stage/"script_tts.json"),
        "slides":rows,"total_cues":4,"publication_allowed":False,
    }),encoding="utf8")
    return stage


def sample_wav(text:str, spec:dict) -> bytes:
    content=io.BytesIO()
    with wave.open(content,"wb") as wav:
        wav.setparams((1,2,8000,0,"NONE","not compressed"))
        wav.writeframes(bytes([len(text)%128,0])*4800)
    return content.getvalue()


def test_global_gemini_flash_lite_and_exact_pcm(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    stage=input_stage(tmp_path)
    original=sha(stage/"slides.pdf")
    calls=[]
    def speaker(text,spec):
        calls.append((text,spec["provider"],spec["voice"]))
        return sample_wav(text,spec)
    report=produce_measured_cue_audio(stage,speak=speaker)
    assert report["cue_count"]==4
    assert report["slide_count"]==2
    assert report["provider"]=="gemini_flash_lite_tts"
    assert report["voice"]=="Kore"
    assert len(calls)==4
    assert {x[1] for x in calls}=={"gemini_flash_lite_tts"}
    assert {x[2] for x in calls}=={"Kore"}
    checked=inspect_timed_highlights(stage)
    assert checked["slide_count"]==2
    assert len(checked["slides"][1]["elements"])==2
    assert (stage/"slide1.wav").exists()
    assert (stage/"highlight_chunks"/"slide2_cue2.wav").exists()
    raw=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    texts=[normalize_scientific_speech(row["tts_text"])
           for row in raw["slides"]]
    tts=verify_manifest(stage,texts)
    assert tts["provider"]=="gemini_flash_lite_tts"
    assert sha(stage/"slides.pdf")==original
    with pytest.raises(CueTTSError,match="Existing"):
        produce_measured_cue_audio(stage,speak=speaker)
    assert len(calls)==4


def test_fallback_regenerates_entire_global_batch_not_mixed(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    stage=input_stage(tmp_path)
    calls=[]
    def speaker(text,spec):
        calls.append(spec["provider"])
        if spec["provider"]=="gemini_flash_lite_tts":
            raise RuntimeError("temporary provider failure")
        return sample_wav(text,spec)
    report=produce_measured_cue_audio(stage,speak=speaker)
    assert report["provider"]=="gemini_flash_tts"
    assert calls==["gemini_flash_lite_tts"]+["gemini_flash_tts"]*4
    assert inspect_timed_highlights(stage)["slide_count"]==2


def test_failed_paid_fallback_preserves_all_source_and_audio(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    stage=input_stage(tmp_path)
    before={x.name:sha(x) for x in stage.glob("*") if x.is_file()}
    def fail(text,spec):
        raise RuntimeError("provider offline")
    with pytest.raises(RuntimeError,match="TTS batch failed"):
        produce_measured_cue_audio(stage,speak=fail)
    assert not list(stage.glob("slide*.wav"))
    assert not (stage/MANIFEST).exists()
    assert not (stage/"highlight_chunks").exists()
    assert {x.name:sha(x) for x in stage.glob("*") if x.is_file()}==before


def test_tampered_plan_preflight_refuses_billable_audio(tmp_path):
    stage=input_stage(tmp_path)
    plan=stage/PLAN_FILE
    data=json.loads(plan.read_text(encoding="utf8"))
    data["slides"][0]["cues"][0]["spoken_text"]="An invented result."
    plan.write_text(json.dumps(data),encoding="utf8")
    called=[]
    with pytest.raises(CueTTSError,match="Cue plan changes"):
        produce_measured_cue_audio(stage,speak=lambda *args:called.append(1))
    assert called==[]


def test_existing_audio_is_never_overwritten(tmp_path):
    stage=input_stage(tmp_path)
    protected=stage/"slide1.wav"
    protected.write_bytes(b"pre-existing accepted wav")
    calls=[]
    with pytest.raises(CueTTSError,match="Existing"):
        produce_measured_cue_audio(stage,speak=lambda *args:calls.append(1))
    assert protected.read_bytes()==b"pre-existing accepted wav"
    assert calls==[]


def test_source_drift_during_tts_fails_without_writes(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    stage=input_stage(tmp_path)
    calls=[]
    def speaker(text,spec):
        if not calls:
            with (stage/"script_tts.json").open("a",encoding="utf8") as f:
                f.write(" ")
        calls.append(1)
        return sample_wav(text,spec)
    with pytest.raises(CueTTSError,match="Source changed"):
        produce_measured_cue_audio(stage,speak=speaker)
    assert not (stage/MANIFEST).exists()
    assert not list(stage.glob("slide*.wav"))
    assert not (stage/"highlight_chunks").exists()
