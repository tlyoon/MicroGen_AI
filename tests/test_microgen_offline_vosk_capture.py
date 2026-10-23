import json
import sys
import types
import wave
import pytest
from microgen_source_safe_orchestrator import digest
from microgen_offline_vosk_capture import (
    OfflineRecognitionError,validate_vosk_words,_decode_to_raw,capture_offline_words
)

def sample_wav(path):
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(bytes(32000))

def test_word_clocks_and_confidence_are_bounded():
    valid=[{"word":"circle","start":0.10,"end":0.28,"conf":0.91}]
    assert validate_vosk_words(valid)[0]["word"]=="circle"
    with pytest.raises(OfflineRecognitionError):
        validate_vosk_words([{"word":"circle","start":-1,"end":0.4,"conf":.91}])
    with pytest.raises(OfflineRecognitionError):
        validate_vosk_words([{"word":"circle","start":0.1,"end":0.4,"conf":1.2}])

def test_actual_wave_pcm_decode_has_original_source_sha(tmp_path):
    from imageio_ffmpeg import get_ffmpeg_exe
    p=tmp_path/"test.wav";sample_wav(p)
    raw,sha=_decode_to_raw(p,get_ffmpeg_exe())
    assert len(raw)==32000
    assert sha==digest(p)

def test_injected_recognizer_yields_unapproved_timestamps(tmp_path,monkeypatch):
    from imageio_ffmpeg import get_ffmpeg_exe
    p=tmp_path/"test.wav";sample_wav(p)
    class FakeRecognizer:
        def __init__(self,model,rate):
            assert rate==16000
        def SetWords(self,enabled):
            assert enabled
        def AcceptWaveform(self,chunk):
            assert chunk
            return False
        def FinalResult(self):
            return json.dumps({"result":[{"word":"see","start":0.4,"end":0.6,"conf":.8}]})
    monkeypatch.setitem(sys.modules,"vosk",
         types.SimpleNamespace(KaldiRecognizer=FakeRecognizer))
    report=capture_offline_words(p,object(),get_ffmpeg_exe())
    assert report["source_wav_sha256"]==digest(p)
    assert report["words"][0]["word"]=="see"
    assert not report["phonetic_identity_verified"]
    assert not report["semantic_word_alignment_certified"]

def test_offline_model_must_exist_no_implicit_download(tmp_path):
    from microgen_offline_vosk_capture import capture_review_bundle
    with pytest.raises((OfflineRecognitionError,FileNotFoundError)):
        capture_review_bundle(tmp_path,tmp_path/"model_missing",
            tmp_path/"ffmpeg",tmp_path/"report.json")
    assert not (tmp_path/"report.json").exists()
