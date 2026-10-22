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
