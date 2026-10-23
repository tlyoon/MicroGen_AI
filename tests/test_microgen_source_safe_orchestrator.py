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

def test_workspace_outside_source_and_sealed(tmp_path):
    src=fixture(tmp_path)
    dst=tmp_path/"stage"
    r=o.create_workspace(src,dst)
    assert (dst/"workspace_receipt.json").is_file()
    assert not r["receipt"]["publication_permitted"]
    with pytest.raises(Exception):o.create_workspace(src,src/"illegal")
    with pytest.raises(Exception):o.create_workspace(src,dst)

def test_workspace_detects_drift_and_forged_approval(tmp_path):
    src=fixture(tmp_path);dst=tmp_path/"stage";o.create_workspace(src,dst)
    assert o.verify_workspace(dst)["slide_count"]==2
    script=src/"script_tts.json";script.write_text(script.read_text()+" ")
    with pytest.raises(o.OrchestratorError):o.verify_workspace(dst)

def test_root_wav_staging_copies_only_existing_tracks(tmp_path):
    src=fixture(tmp_path);write_wave(src/"slide2.wav",.5)
    dst=tmp_path/"stage";o.create_workspace(src,dst)
    report=o.stage_existing_root_wavs(dst)
    assert report["copied"]==1 and report["missing"]==[1]
    assert o.digest(dst/"audio"/"slide2.wav")==o.digest(src/"slide2.wav")

def test_qa_candidates_remain_unverified(tmp_path):
    src=fixture(tmp_path);qa=src/"QA_audio";qa.mkdir()
    write_wave(qa/"slide1_corrected.wav",.4)
    report=o.discover_qa_audio_candidates(src)
    assert len(report["candidates"])==1
    assert report["candidates"][0]["approved_for_reuse"] is False

def test_explicit_wav_adoption_checks_text_and_hash(tmp_path):
    src=fixture(tmp_path);dst=tmp_path/"stage";o.create_workspace(src,dst)
    o.stage_existing_root_wavs(dst)
    offered=tmp_path/"candidate.wav";write_wave(offered,.4)
    rows=json.loads((src/"script_tts.json").read_text())["slides"]
    from microgen_pipeline_completion import _tts_digest
    proof=_tts_digest(rows[0])
    with pytest.raises(o.OrchestratorError):
        o.adopt_verified_wav(dst,1,offered,sha256="0"*64,narration_sha256=proof)
    assert o.adopt_verified_wav(dst,1,offered,sha256=o.digest(offered),narration_sha256=proof)["adopted"]==1
