"""Resume exact WAV-bound Vosk hypotheses without moving old clock times."""
import json
import sys
import types
from pathlib import Path

import pytest

import microgen_resumable_corrected_asr as unit
from microgen_source_safe_orchestrator import atomic_json,digest
from test_microgen_corrected_audio_stage import _fixture
from microgen_corrected_audio_stage import prepare_section25_corrected_wavs


def _ready(tmp_path,monkeypatch):
    source,recovery,selection,_=_fixture(tmp_path)
    stage=tmp_path/"corrected_stage"
    prepare_section25_corrected_wavs(recovery,selection,stage)
    model=tmp_path/"vosk-model-small-en-us-0.15"
    (model/"am").mkdir(parents=True)
    (model/"am"/"final.mdl").write_bytes(b"synthetic weights")
    (model/"graph").mkdir()
    (model/"graph"/"HCLr.fst").write_bytes(b"synthetic graph")
    exe=tmp_path/"ffmpeg.exe"
    exe.write_bytes(b"not a real executable; mocked")
    calls=[]
    monkeypatch.setitem(sys.modules,"vosk",types.SimpleNamespace(Model=lambda _:object()))
    def observe(wav,_model,_ffmpeg):
        i=int(Path(wav).stem[5:])
        calls.append(i)
        return {"source_wav_sha256":digest(wav),"file":Path(wav).name,
                "words":[{"word":"source","start":.01,"end":.12,"conf":.99}],
                "phonetic_identity_verified":False,
                "semantic_word_alignment_certified":False}
    monkeypatch.setattr(unit,"capture_offline_words",observe)
    return stage,model,exe,calls


def test_resumable_batches_do_not_reprocess_slides(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    out=tmp_path/"new_progress"
    a=unit.resume_current_audio_asr(stage,model,exe,out,max_new_slides=3)
    assert a["status"]=="OFFLINE_ASR_RESUMABLE_PROGRESS"
    assert a["verified_slides"]==3 and calls==[1,2,3]
    assert not (out/"asr_current_audio.json").exists()
    b=unit.resume_current_audio_asr(stage,model,exe,out,max_new_slides=14)
    assert b["status"]=="OFFLINE_ASR_CANDIDATE_COMPLETE"
    assert b["verified_slides"]==17
    assert calls==list(range(1,18))
    report=json.loads((out/"asr_current_audio.json").read_text())
    assert report["status"]=="CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH"
    assert len(report["results"])==17
    assert report["phonetic_identity_verified"] is False
    assert report["publication_allowed"] is False
    with pytest.raises(unit.CurrentASRCheckpointError,match="finalized"):
        unit.resume_current_audio_asr(stage,model,exe,out)

def test_current_report_works_with_conservative_source_pdf_cue_builder(tmp_path,monkeypatch):
    from microgen_corrected_cue_realign import regenerate_stage_cues
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    out=tmp_path/"new_progress"
    unit.resume_current_audio_asr(stage,model,exe,out)
    result=regenerate_stage_cues(stage,out/"asr_current_audio.json")
    assert result["slides"]==17
    assert result["cue_count"]>=1
    cue=json.loads((stage/"cues.json").read_text())
    assert cue["publication_allowed"] is False
    assert cue["spoken_word_alignment_verified"] is False
    assert cue["version"]==2

def test_changed_model_blocks_resume_without_overwriting(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    progress=tmp_path/"progress"
    unit.resume_current_audio_asr(stage,model,exe,progress,max_new_slides=2)
    original=(progress/"slide01.json").read_bytes()
    (model/"am"/"final.mdl").write_bytes(b"tampered")
    with pytest.raises(unit.CurrentASRCheckpointError,match="provenance"):
        unit.resume_current_audio_asr(stage,model,exe,progress)
    assert (progress/"slide01.json").read_bytes()==original
    assert calls==[1,2]

def test_changed_audio_blocks_resume_and_rejects_old_times(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    progress=tmp_path/"progress"
    unit.resume_current_audio_asr(stage,model,exe,progress,max_new_slides=1)
    (stage/"audio"/"slide7.wav").write_bytes(b"changed")
    with pytest.raises(ValueError,match="Audio is not an intact WAV|audio SHA"):
        unit.resume_current_audio_asr(stage,model,exe,progress)
    assert calls==[1]

@pytest.mark.parametrize("where",["stage","model","source","existingfile"])
def test_does_not_write_to_protected_or_existing_destinations(tmp_path,monkeypatch,where):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    src=Path(unit.verify_workspace(stage)["source_root"])
    dest={"stage":stage/"progress","model":model/"progress",
          "source":src/"progress","existingfile":tmp_path/"file"}[where]
    if where=="existingfile":dest.write_bytes(b"do not overwrite")
    with pytest.raises(unit.CurrentASRCheckpointError):
        unit.resume_current_audio_asr(stage,model,exe,dest)
    assert calls==[]

def test_bad_checkpoint_receipt_cannot_skip_missing_recognition(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    progress=tmp_path/"progress"
    unit.resume_current_audio_asr(stage,model,exe,progress,max_new_slides=1)
    p=progress/"slide01.json"
    record=json.loads(p.read_text())
    record["phonetic_identity_verified"]=True
    atomic_json(p.with_name("corrupted.json"),record)
    p.unlink()
    (progress/"corrupted.json").rename(p)
    with pytest.raises(unit.CurrentASRCheckpointError):
        unit.resume_current_audio_asr(stage,model,exe,progress)
    assert calls==[1]

def test_missing_runtime_package_retains_existing_progress(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    progress=tmp_path/"progress"
    unit.resume_current_audio_asr(stage,model,exe,progress,max_new_slides=1)
    monkeypatch.setitem(sys.modules,"vosk",None)
    with pytest.raises(unit.CurrentASRCheckpointError,match="unavailable"):
        unit.resume_current_audio_asr(stage,model,exe,progress)
    assert (progress/"slide01.json").is_file()
    assert calls==[1]


def test_empty_asr_words_do_not_create_false_completed_slide(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    def zero(wav,unused_model,unused_ffmpeg):
        return {"source_wav_sha256":digest(wav),"file":Path(wav).name,
                "words":[],"phonetic_identity_verified":False,
                "semantic_word_alignment_certified":False}
    monkeypatch.setattr(unit,"capture_offline_words",zero)
    out=tmp_path/"progress"
    with pytest.raises(unit.CurrentASRCheckpointError,match="Empty ASR"):
        unit.resume_current_audio_asr(stage,model,exe,out)
    assert (out/"session.json").exists()
    assert not (out/"slide01.json").exists()
    assert not (out/"asr_current_audio.json").exists()


def test_inference_interruption_retains_two_valid_slides_then_resumes(tmp_path,monkeypatch):
    stage,model,exe,calls=_ready(tmp_path,monkeypatch)
    good=unit.capture_offline_words
    def one_failure(wav,recognizer,ffmpeg):
        if Path(wav).stem=="slide3":
            raise RuntimeError("simulated interruption after two complete slides")
        return good(wav,recognizer,ffmpeg)
    monkeypatch.setattr(unit,"capture_offline_words",one_failure)
    out=tmp_path/"progress"
    with pytest.raises(RuntimeError,match="interruption"):
        unit.resume_current_audio_asr(stage,model,exe,out)
    first=(out/"slide01.json").read_bytes()
    second=(out/"slide02.json").read_bytes()
    assert not (out/"slide03.json").exists()
    monkeypatch.setattr(unit,"capture_offline_words",good)
    result=unit.resume_current_audio_asr(stage,model,exe,out)
    assert result["verified_slides"]==17
    assert (out/"slide01.json").read_bytes()==first
    assert (out/"slide02.json").read_bytes()==second
    assert calls==list(range(1,18))
