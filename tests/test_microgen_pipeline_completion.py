"""Offline realistic/adversarial production completion tests."""
import json,hashlib,struct,wave,math
from pathlib import Path
import pytest
import pymupdf as fitz
import microgen_pipeline_completion as m

def make_source(root):
    with fitz.open() as doc:
        for i in (1,2):
            page=doc.new_page(width=640,height=360)
            page.insert_text((35,60),"limit as x approaches c.",fontsize=18)
        doc.save(root/"slides.pdf")
    rows=[{"slide":i,"tts_text":f"At c. {i}"} for i in (1,2)]
    (root/"script_tts.json").write_text(json.dumps({"slides":rows}),encoding="utf8")
def write_wav(path,seconds,amplitude=0):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(struct.pack("<h",amplitude)*int(16000*seconds))

def test_source_contract_is_finite_and_blocking(tmp_path):
    make_source(tmp_path)
    c=m.production_contract(tmp_path)
    assert c["slide_count"]==2 and not c["source_audio_complete"]
    assert c["next_action"]=="RECOVER_OR_SYNTHESIZE_MISSING_AUDIO"
    assert not c["ready_for_publication"]

def test_audio_recovery_rejects_wrong_narration_and_does_not_write_source(tmp_path):
    src=tmp_path/"source";src.mkdir();make_source(src)
    wave_file=tmp_path/"offered.wav";write_wav(wave_file,.3)
    entries=[{"slide":i,"path":str(wave_file),"wav_sha256":m._sha(wave_file),
               "narration_sha256":m._tts_digest({"tts_text":f"At c. {i}"})} for i in (1,2)]
    originals=(src/"script_tts.json").read_bytes()
    r=m.recover_source_bound_wavs(src,tmp_path/"recovered",entries)
    assert (Path(r["audio_stage"])/"slide2.wav").is_file()
    assert (src/"script_tts.json").read_bytes()==originals
    entries[1]["narration_sha256"]="f"*64
    with pytest.raises(m.CampaignError):
        m.recover_source_bound_wavs(src,tmp_path/"another",entries)
    assert not (tmp_path/"another").exists()
