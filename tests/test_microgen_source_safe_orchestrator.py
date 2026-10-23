"""Offline staged production behavior; no real provider or publishing calls."""
import hashlib,json,struct,wave
from pathlib import Path
import pytest
import pymupdf as fitz
import microgen_source_safe_orchestrator as o

def fixture(root):
    src=root/"lesson";src.mkdir()
    with fitz.open() as doc:
        for i in (1,2):
            page=doc.new_page(width=640,height=360)
            page.insert_text((35,62),"limit approaches c",fontsize=17)
        doc.save(src/"slides.pdf")
    (src/"script_tts.json").write_text(json.dumps({"slides":[
        {"slide":1,"tts_text":"At c. Next take the limit."},
        {"slide":2,"tts_text":"At c. Next take the limit."}]}),encoding="utf8")
    return src

def write_wave(p,seconds=0.8,amplitude=9000):
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(struct.pack("<h",amplitude)*round(seconds*16000))

def test_inventory_reports_real_missing_wavs(tmp_path):
    src=fixture(tmp_path)
    write_wave(src/"slide1.wav",.4)
    x=o.source_audio_inventory(src)
    assert x["missing"]==[2] and x["slides"][0]["sha256"]
    assert not x["wave_provenance_verified"]
