"""Real PDF rendering fixture, current audio clocks, no invented word cues."""
import json
import wave
from pathlib import Path
from types import SimpleNamespace
import pytest

import microgen_corrected_slide_clock as u
from microgen_corrected_audio_stage import prepare_section25_corrected_wavs
from microgen_source_safe_orchestrator import atomic_json,digest
from test_microgen_corrected_audio_stage import _fixture

def _ready(tmp_path):
    src,recovery,selection,_=_fixture(tmp_path)
    stage=tmp_path/"corrected_stage"
    prepare_section25_corrected_wavs(recovery,selection,stage)
    sh=tmp_path/"shadow";sh.mkdir()
    clips=[]
    with wave.open(str(sh/"section25_corrected_shadow_UNAPPROVED.wav"),"wb") as dest:
        dest.setnchannels(1);dest.setsampwidth(2);dest.setframerate(16000)
        for i in range(1,18):
            with wave.open(str(stage/"audio"/f"slide{i}.wav"),"rb") as clip:
                dest.writeframes(clip.readframes(clip.getnframes()))
        # explicit old-source AAC tail technical analogue
        dest.writeframes(b"\0\0"*1600)
    wav=sh/"section25_corrected_shadow_UNAPPROVED.wav"
    with wave.open(str(wav),"rb") as a:
        seconds=a.getnframes()/16000
    atomic_json(sh/"shadow_receipt.json",{
        "status":"COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM",
        "corrected_slides":[5,6,10],"shadow_sha256":digest(wav),
        "all_preexisting_ASR_cue_timing_invalidated":True,
        "tail_seconds":0.1,"audio_seconds":seconds,
        "publication_allowed":False})
    return src,stage,selection,sh

def test_measured_current_wav_clocks_include_corrected_slides_and_tail(tmp_path):
    src,stage,sel,sh=_ready(tmp_path)
    plan=u.build_slide_clock(stage,sel,sh)
    assert len(plan["segments"])==17
    assert plan["segments"][5]["start"]==pytest.approx(1.11)
    assert plan["tail_seconds"]==pytest.approx(.1)
    assert not (stage/"cues.json").exists()
    assert plan["pcm"]["pcm_seconds"]==pytest.approx(plan["audio_seconds"])

@pytest.mark.parametrize("tamper",["wav","receipt","timeline","shadow","approval"])
def test_corrupt_slide_clock_or_audio_is_rejected(tmp_path,tamper):
    _,stage,sel,sh=_ready(tmp_path)
    if tamper=="wav":(stage/"audio"/"slide9.wav").write_bytes(b"broken")
    if tamper=="receipt":
        p=sel/"selection_receipt.json";d=json.loads(p.read_text());d["other"]=1;atomic_json(p,d)
    if tamper=="timeline":
        p=stage/"measured_timeline.json";d=json.loads(p.read_text())
        d["slide_intervals"][5]["start_seconds"]=5.;atomic_json(p,d)
    if tamper=="shadow":
        (sh/"section25_corrected_shadow_UNAPPROVED.wav").write_bytes(b"changed")
    if tamper=="approval":
        p=sh/"shadow_receipt.json";d=json.loads(p.read_text());d["publication_allowed"]=True;atomic_json(p,d)
    with pytest.raises((u.CorrectedSlidesError,ValueError)):
        u.build_slide_clock(stage,sel,sh)

def test_rendered_slide_video_preserves_shadow_pcm_and_pdf_page_order(tmp_path,monkeypatch):
    src,stage,sel,sh=_ready(tmp_path)
    ff=tmp_path/"ffmpeg.exe";ff.write_bytes(b"dummy")
    monkeypatch.setattr(u,"check_video",lambda *a,**kw:{"seconds":u.build_slide_clock(stage,sel,sh)["audio_seconds"]})
    monkeypatch.setattr(u,"_decoded_audio_hash",
        lambda *a,**kw:u.build_slide_clock(stage,sel,sh)["pcm"])
    def mock_render(cmd,**kw):
        assert cmd[cmd.index("-vf")+1]=="fps=8"
        assert cmd[cmd.index("-fps_mode")+1]=="cfr"
        Path(cmd[-1]).write_bytes(b"candidate")
        return SimpleNamespace(returncode=0,stderr=b"")
    monkeypatch.setattr(u.subprocess,"run",mock_render)
    out=tmp_path/"rendered"
    result=u.render_corrected_slide_clock(stage,sel,sh,out,ffmpeg=ff)
    assert result["pcm_verified"] is True
    assert result["slide_pixels_independently_verified"] is False
    assert result["publication_allowed"] is False
    script=(out/"frames.ffconcat").read_text()
    assert script.count("duration")==18
    assert "slide17.png" in script
    assert not (src/"cues.json").exists()

def test_no_existing_or_source_folder_overwrite(tmp_path):
    src,stage,sel,sh=_ready(tmp_path)
    ff=tmp_path/"ffmpeg.exe";ff.write_bytes(b"dummy")
    for dest in (src/"candidate",sh/"candidate",tmp_path):
        with pytest.raises(u.CorrectedSlidesError,match="brand-new"):
            u.render_corrected_slide_clock(stage,sel,sh,dest,ffmpeg=ff)
