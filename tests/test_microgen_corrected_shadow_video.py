import copy
import json
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
import microgen_corrected_shadow_video as v
from microgen_source_safe_orchestrator import atomic_json, digest


def _fixture(tmp_path, monkeypatch):
    src=tmp_path/"protected_source"
    src.mkdir()
    (src/"slides.mp4").write_bytes(b"fake original video")
    rec=tmp_path/"recovery"; rec.mkdir()
    sel=tmp_path/"selection"; sel.mkdir()
    sh=tmp_path/"shadow"; sh.mkdir()
    wav=sh/"section25_corrected_shadow_UNAPPROVED.wav"
    with wave.open(str(wav),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(struct.pack("<h",37)*32000)
    clip=[{"slide":i,"sha256":str(i)*64} for i in range(1,18)]
    trials=[{"slide":i,"wav_sha256":str(i)*64} for i in (5,6,10)]
    receipt={"source_root":str(src),"slide_count":17,
             "source_pdf_sha256":"a"*64,"narration_sha256":"b"*64}
    monkeypatch.setattr(v,"verify_workspace",lambda _:receipt)
    original=digest(src/"slides.mp4")
    atomic_json(rec/"legacy_mp4_audio_receipt.json",{
        "status":"PROVISIONAL_NOT_PUBLISHABLE",
        "scene_evidence":{"mp4_sha256":original},"clips":clip})
    atomic_json(sel/"selection_receipt.json",{
        "status":"SHADOW_ONLY_TRIAL_SELECTION","publication_allowed":False,
        "source_pdf_sha256":"a"*64,"source_narration_sha256":"b"*64,
        "source_mp4_sha256":original,"trials":trials})
    segments=[{"slide":i,"original_sha256":str(i)*64,
               "new_word_timing_required":i in (5,6,10)}
              for i in range(1,18)]
    report={"status":"COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM",
            "publication_allowed":False,"corrected_slides":[5,6,10],
            "shadow_wav":str(wav),"shadow_sha256":digest(wav),
            "audio_seconds":2.,"audio_segments":segments,
            "all_preexisting_ASR_cue_timing_invalidated":True}
    atomic_json(sh/"shadow_receipt.json",report)
    ff=tmp_path/"ffmpeg.exe";ff.write_bytes(b"fake binary")
    monkeypatch.setattr(v,"require_tail_ffmpeg_capabilities",lambda _:ff)
    monkeypatch.setattr(v,"check_video",lambda p,**kw:{
        "seconds":2. if "NO_HIGHLIGHT" in str(p) else 1.5})
    monkeypatch.setattr(v,"_decoded_audio_hash",lambda *a,**kw:v._pcm_properties(wav))
    def fake_render(command,capture_output,timeout):
        Path(command[-1]).write_bytes(b"candidate movie")
        return SimpleNamespace(returncode=0,stderr=b"")
    monkeypatch.setattr(v.subprocess,"run",fake_render)
    return src,rec,sel,sh,ff


def test_video_candidate_pcm_matches_and_is_explicitly_unapproved(tmp_path,monkeypatch):
    src,rec,sel,sh,ff=_fixture(tmp_path,monkeypatch)
    out=tmp_path/"fresh_candidate"
    result=v.render_corrected_shadow_video(rec,sel,sh,out,ffmpeg=ff)
    receipt=json.loads((out/"corrected_shadow_video_receipt.json").read_text())
    assert result["exact_corrected_pcm_preserved"] is True
    assert receipt["corrected_audio_samples"]==32000
    assert receipt["highlight_cues_present"] is False
    assert receipt["publication_allowed"] is False
    assert digest(src/"slides.mp4")==receipt["source_mp4_sha256"]

@pytest.mark.parametrize("mutate",["wav","wrong_slide","approval","clock","old_cues","source","selection"])
def test_bad_inputs_refused_before_media_creation(tmp_path,monkeypatch,mutate):
    src,rec,sel,sh,ff=_fixture(tmp_path,monkeypatch)
    if mutate=="wav":
        (sh/"section25_corrected_shadow_UNAPPROVED.wav").write_bytes(b"tamper")
    if mutate=="wrong_slide":
        p=sh/"shadow_receipt.json"
        record=json.loads(p.read_text())
        record["audio_segments"][0]["original_sha256"]="f"*64
        atomic_json(p,record)
    if mutate=="approval":
        p=sh/"shadow_receipt.json";record=json.loads(p.read_text())
        record["publication_allowed"]=True;atomic_json(p,record)
    if mutate=="clock":
        p=sh/"shadow_receipt.json";record=json.loads(p.read_text())
        record["audio_seconds"]=620;atomic_json(p,record)
    if mutate=="old_cues":
        p=sh/"shadow_receipt.json";record=json.loads(p.read_text())
        record["all_preexisting_ASR_cue_timing_invalidated"]=False;atomic_json(p,record)
    if mutate=="source":
        (src/"slides.mp4").write_bytes(b"tampered source")
    if mutate=="selection":
        p=sel/"selection_receipt.json";record=json.loads(p.read_text())
        record["source_pdf_sha256"]="f"*64;atomic_json(p,record)
    out=tmp_path/"candidate"
    with pytest.raises((v.CorrectedShadowVideoError,EOFError,wave.Error)):
        v.render_corrected_shadow_video(rec,sel,sh,out,ffmpeg=ff)
    assert not out.exists()

def test_existing_destination_refuses_rewrite(tmp_path,monkeypatch):
    _,rec,sel,sh,ff=_fixture(tmp_path,monkeypatch)
    out=tmp_path/"already";out.mkdir()
    with pytest.raises(v.CorrectedShadowVideoError,match="separate"):
        v.render_corrected_shadow_video(rec,sel,sh,out,ffmpeg=ff)

def test_video_pcm_mismatch_erases_only_failed_new_candidate(tmp_path,monkeypatch):
    src,rec,sel,sh,ff=_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(v,"_decoded_audio_hash",lambda *args:{"pcm_sha256":"bad"})
    out=tmp_path/"candidate"
    with pytest.raises(v.CorrectedShadowVideoError,match="PCM"):
        v.render_corrected_shadow_video(rec,sel,sh,out,ffmpeg=ff)
    assert not out.exists()
    assert (src/"slides.mp4").read_bytes()==b"fake original video"
