"""Offline ASR contrast is diagnostic only and requires real WAV SHA bindings."""
import json
import wave
from pathlib import Path
import pytest
from microgen_source_safe_orchestrator import digest
from microgen_offline_pronunciation_contrast import ASRContrastError,assess_pronunciation_contrast

def _wav(p):
    p.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(bytes(32000))

def _json(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data),encoding="utf8")

def _row(path,tokens):
    return {"file":path.name,"source_wav_sha256":digest(path),
            "phonetic_identity_verified":False,
            "semantic_word_alignment_certified":False,
            "words":[{"word":s,"start":i*.4,"end":i*.4+.2,
                      "conf":.95} for i,s in enumerate(tokens)]}

def _bundle(tmp_path):
    base=tmp_path/"bundle"
    old=base/"original_scene_references"/"slide06_reference.wav"
    new=base/"unapproved_trials"/"slide06_CDOT_UNREVIEWED.wav"
    _wav(old);_wav(new)
    _json(base/"review_manifest.json",{
        "status":"TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED",
        "publication_allowed":False,
        "source_mp4_sha256":"a"*64,"narration_sha256":"b"*64,
        "slides_to_review":[6],
        "historical_audio_candidates":[
            {"slide":6,"risk_class":"CDOT","wav_sha256":digest(new),
             "publication_allowed":False,"phonetic_approved":False,
             "source_media_receipt_bound":True}]})
    asr={"model":"test-recognizer",
         "model_word_timestamps_not_ground_truth":True,
         "publication_allowed":False,"results":[
             _row(old,["circa","circa"]),
             _row(new,["see","see"])]}
    path=tmp_path/"recognitions.json";_json(path,asr)
    return base,path,new

def test_circumstantial_asr_delta_cannot_authorize_replacement(tmp_path):
    folder,asr,_=_bundle(tmp_path)
    report=assess_pronunciation_contrast(folder,asr)
    item=report["candidate_assessments"][0]
    assert item["assessment"]=="AUTOMATED_CONTRAST_SUGGESTS_CIRCA_REDUCED"
    assert len(item["old_suspect_words"])==2
    assert not item["eligible_for_replacement"]
    assert not report["phonetic_accuracy_verified"]
    assert not report["publication_allowed"]

def test_changed_wav_invalidates_saved_recognizer(tmp_path):
    folder,asr,new=_bundle(tmp_path)
    with new.open("ab") as f:f.write(b"tamper")
    with pytest.raises(ASRContrastError):
        assess_pronunciation_contrast(folder,asr)

def test_spoofed_transcription_approval_is_rejected(tmp_path):
    folder,asr,_=_bundle(tmp_path)
    j=json.loads(asr.read_text())
    j["results"][0]["phonetic_identity_verified"]=True
    _json(asr,j)
    with pytest.raises(ASRContrastError):
        assess_pronunciation_contrast(folder,asr)

def test_invalid_word_timing_fails_closed(tmp_path):
    folder,asr,_=_bundle(tmp_path)
    j=json.loads(asr.read_text())
    j["results"][0]["words"][1]["start"]=-2
    _json(asr,j)
    with pytest.raises(ASRContrastError):
        assess_pronunciation_contrast(folder,asr)
