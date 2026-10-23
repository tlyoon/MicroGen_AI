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

def test_speech_inputs_normalize_cdot_without_changing_original(tmp_path):
    make_source(tmp_path)
    file=tmp_path/"script_tts.json"
    rows=json.loads(file.read_text(encoding="utf8"))
    rows["slides"][0]["tts_text"]="At c. Next, take the limit."
    file.write_text(json.dumps(rows),encoding="utf8")
    before=file.read_bytes()
    result=m.produce_spoken_inputs(tmp_path)
    assert "see." in result["slides"][0]["speech_input"]
    assert result["provider_called"] is False
    assert (tmp_path/"script_tts.json").read_bytes()==before

def test_regenerator_retries_and_keeps_voice_and_source(tmp_path):
    src=tmp_path/"src";src.mkdir();make_source(src)
    calls=[]
    def backend(text,output,**kw):
        calls.append(kw)
        if len(calls)<3:raise RuntimeError("test offline synthesized failure")
        write_wav(output,.3)
        return dict(kw)
    result=m.regenerate_staged_wav(src,tmp_path/"isolated",1,backend)
    assert result["status"]=="REVIEW_REQUIRED" and len(calls)==3
    assert len({v["voice"] for v in calls})==1
    assert not (src/"slide1.wav").exists()

def test_activity_detection_uses_real_nonzero_pcm(tmp_path):
    p=tmp_path/"speech.wav";write_wav(p,.2,amplitude=9000)
    x=m.observe_acoustic_activity(p)
    assert x["activity_intervals_seconds"] and not x["word_alignment_verified"]
    silence=tmp_path/"silence.wav";write_wav(silence,.2)
    assert m.observe_acoustic_activity(silence)["activity_intervals_seconds"]==[]

def test_mapping_requires_unambiguous_real_pdf_word(tmp_path):
    make_source(tmp_path)
    for n in (1,2):write_wav(tmp_path/f"slide{n}.wav",.4)
    t=m._timeline(tmp_path,2)
    cue={"slide":1,"word":"limit","start_seconds":.1,"end_seconds":.3,"spoken_phrase":"limit"}
    r=m.bind_narration_anchors(tmp_path/"slides.pdf",t,[cue])
    assert r["real_pdf_geometry_verified"] and not r["narration_phrase_timing_ground_truth_verified"]
    with pytest.raises(m.CampaignError):
       m.bind_narration_anchors(tmp_path/"slides.pdf",t,[{**cue,"word":"notfound"}])
