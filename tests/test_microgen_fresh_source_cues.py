"""Fail-closed independent cue-binding tests for new 23-WAV TTS source."""
import json
import wave
from pathlib import Path
import pymupdf as fitz
import pytest
import microgen_fresh_source_cues as s


def test_unique_word_cues_filter_repeat_low_confidence_and_short_duration():
    pdf=fitz.open();p=pdf.new_page();p.insert_text((45,60),"Derivative theorem theorem gradient integral 1234")
    rows=[{"word":"derivative","start":.2,"end":.6,"conf":.99},
          {"word":"theorem","start":.7,"end":1.0,"conf":.99},
          {"word":"theorem","start":1.1,"end":1.4,"conf":.99},
          {"word":"gradient","start":1.5,"end":1.8,"conf":.40},
          {"word":"integral","start":1.9,"end":1.94,"conf":.99}]
    items=s._cue_candidates(p,rows,3)
    assert [x["text"] for x in items]==["derivative"]
    assert len(items[0]["box"])==4


def test_no_missing_wav_may_pretend_success(tmp_path):
    f=fitz.open();f.new_page();f.new_page();f.save(tmp_path/"slides.pdf");f.close()
    with pytest.raises(s.FreshCueError,match="Missing regular WAV"):
        s.source_inventory(tmp_path)


def test_audios_are_hash_bound(tmp_path):
    f=fitz.open();f.new_page();f.new_page();f.save(tmp_path/"slides.pdf");f.close()
    for i in (1,2):
        with wave.open(str(tmp_path/f"slide{i}.wav"),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
            w.writeframes(b"\x00\x00"*24000)
    _,first=s.source_inventory(tmp_path)
    assert first["slide_count"]==2
    (tmp_path/"slide1.wav").write_bytes((tmp_path/"slide1.wav").read_bytes()+b"x")
    assert s.source_inventory(tmp_path)[1]!=first


def test_pdf_duplicates_and_ambiguous_asr_are_not_matched():
    pdf=fitz.open();p=pdf.new_page()
    p.insert_text((40,50),"Acceleration acceleration")
    obs=[{"word":"acceleration","start":.1,"end":.5,"conf":.99}]
    assert s._cue_candidates(p,obs,1)==[]
