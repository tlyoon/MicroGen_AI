import json,hashlib,struct
from types import SimpleNamespace
import pytest
import microgen_tts_av_evidence as a

def sample_manifest(video_sha):
    return {"schema_version":1,"video_sha256":video_sha,"cues":[{"cue_id":"cue1","slide_number":1,"element_id":"eq1","narration_id":"sentence1","start_seconds":1.0,"end_seconds":2.0,"box":[0,0,2,2],"slide_image_sha256":"b"*64}]}

def test_strict_bounded_audio_window(tmp_path):
    p=tmp_path/"video.mp4";p.write_bytes(b"clip")
    assert a.validate_audio_window(p,1,0.25,duration=599)["sample_rate"]==16000
    for start,sec,dur in [(-1,.2,3),(0,.2,600),(2.9,.2,3),(0,1.01,3),(0,0,3),(0,True,3),(0,.2,float("nan"))]:
        with pytest.raises(a.AudioEvidenceError):a.validate_audio_window(p,start,sec,duration=dur)
    with pytest.raises(a.AudioEvidenceError):a.validate_audio_window(tmp_path/"notfound.mp4",0,.2,duration=3)

def test_ffmpeg_pcm_command_guard_and_failure(tmp_path,monkeypatch):
    p=tmp_path/"lesson.mp4";p.write_bytes(b"video")
    calls=[]
    def runner(cmd,**kw):
        calls.append((cmd,kw))
        return SimpleNamespace(returncode=0,stdout=b"\0"*6400,stderr=b"")
    monkeypatch.setattr(a.subprocess,"run",runner)
    assert len(a.extract_pcm_window(p,1,.2,duration=9))==6400
    assert calls[0][0][:2]==["ffmpeg","-nostdin"]
    assert "-vn" in calls[0][0] and "-map" in calls[0][0]
    assert calls[0][1]["timeout"]==25
    monkeypatch.setattr(a.subprocess,"run",lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout=b"\0",stderr=b""))
    with pytest.raises(a.AudioEvidenceError):a.extract_pcm_window(p,1,.2,duration=9)

def test_pcm_metrics_silence_tone_and_clipping():
    blank=bytes(3200)
    assert a.pcm_energy(blank)["rms"]==0
    tone=struct.pack("<1600h", *([8000]*1600))
    row=a.pcm_energy(tone)
    assert row["sample_count"]==1600 and .2<row["rms"]<.3
    assert row["spoken_words_verified"] is False
    clipped=struct.pack("<800h",*([32767]*800))
    assert a.pcm_energy(clipped)["clipped_fraction"]==1
    for data in (b"",b"\x01",b"x"*40000):
        with pytest.raises(a.AudioEvidenceError):a.pcm_energy(data)

def test_acoustic_threshold_is_not_a_phonetic_label():
    for rms,clip,expect in [(0,0,"BELOW_SPEECH_LIKE_ENERGY_THRESHOLD"),
         (.1,0,"ACOUSTIC_ENERGY_PRESENT"),(.8,.8,"UNRELIABLE_CLIPPED_AUDIO")]:
        result=a.classify_acoustic_activity({"rms":rms,"peak":rms,"clipped_fraction":clip})
        assert result["activity_label"]==expect and not result["speech_or_phonetic_identity_verified"]
    with pytest.raises(a.AudioEvidenceError):
        a.classify_acoustic_activity({"rms":float("inf"),"peak":0,"clipped_fraction":0})

def test_two_audio_windows_and_short_cue_abstention(tmp_path,monkeypatch):
    video=tmp_path/"lesson.mp4";video.write_bytes(b"input")
    monkeypatch.setattr(a,"extract_pcm_window",lambda *args,**kw:struct.pack("<2400h", *([8000]*2400)))
    cue={"cue_id":"e1","start_seconds":1.0,"end_seconds":2.0}
    report=a.probe_audio_cue(video,cue,duration=4)
    assert len(report["samples"])==2 and report["energy_evidence_pass"]
    assert report["spoken_words_verified"] is False
    cue["end_seconds"]=1.15
    assert a.probe_audio_cue(video,cue,duration=4)["status"]=="ABSTAIN_CUE_TOO_SHORT"

def test_audio_source_binding_and_mid_read_tampering(tmp_path,monkeypatch):
    p=tmp_path/"lesson.mp4";p.write_bytes(b"original")
    fp=hashlib.sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(a,"probe_audio_cue",lambda *args,**kw:{"energy_evidence_pass":False})
    assert a.fingerprint_bound_audio_cue(p,fp,{},duration=2)["video_sha256_verified"]
    p.write_bytes(b"tampered")
    with pytest.raises(a.AudioEvidenceError):a.fingerprint_bound_audio_cue(p,fp,{},duration=2)
    p.write_bytes(b"original")
    def tamper(*args,**kw):
        p.write_bytes(b"tampered again")
        return {"energy_evidence_pass":False}
    monkeypatch.setattr(a,"probe_audio_cue",tamper)
    with pytest.raises(a.AudioEvidenceError):a.fingerprint_bound_audio_cue(p,fp,{},duration=2)
