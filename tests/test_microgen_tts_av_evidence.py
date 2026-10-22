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
