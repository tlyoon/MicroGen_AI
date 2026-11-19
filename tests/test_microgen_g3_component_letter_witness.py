"""G3 source-bound a_x/i_x recognition ambiguity: strict third Gemini witness.

No provider calls are made by these tests. A real private HP 21-slide
trace is used only when explicitly supplied by the HP test environment;
no original PDF, WAV, or blind transcripts are placed in Git fixtures.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import wave

import pytest
import microgen_autonomous_acoustic_gate as gate
import microgen_verified_acoustic_replay as replay
from microgen_tts_acoustic_qa import (
    audit_with_recognizer, verified_isolated_component_letter_witness,
    _input_snapshot,
)
from microgen_tts_evidence import verify_acoustic_evidence
from microgen_tts_provenance import make_record, write_manifest, digest_file
from text_to_speech_v25 import normalize_scientific_speech


def correct():
    return (
        "We consider average velocity for constant acceleration. Because "
        "velocity varies linearly in time, the average velocity is the "
        "arithmetic mean of initial and final velocities. Vee sub ex average "
        "equals vee sub ex initial plus vee sub ex final, divided by 2, "
        "for constant ay sub ex. If acceleration changes over time, "
        "this arithmetic mean is no longer valid."
    )


def wrong():
    return correct().replace("for constant ay sub ex",
                             "for constant i sub e x")


def prepare(stage):
    stage.mkdir(parents=True)
    with wave.open(str(stage/"slide1.wav"),"wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00"*24000)
    text=normalize_scientific_speech(correct())
    record=make_record(
        slide=1,path=stage/"slide1.wav",text=text,
        provider="gemini_flash_lite_tts",key="offline-only",
        voice_name="Kore",language_code="en-US",
        speaking_rate=1.0,location="global")
    write_manifest(stage,[record],[text])
    return text


def report_for(stage, text):
    return audit_with_recognizer(
        stage,[text],lambda _:text,lambda x:x,
        independent_recognizer=lambda _:wrong(),
        recognition_models=("gemini-test-3.5","gemini-test-3.8"),
    )


def test_exact_isolated_acceleration_component_needs_third():
    assert verified_isolated_component_letter_witness(
        correct(),correct(),wrong(),correct())
    assert verified_isolated_component_letter_witness(
        correct(),wrong(),correct(),correct())
    assert not verified_isolated_component_letter_witness(
        correct(),correct(),wrong(),wrong())
    assert not verified_isolated_component_letter_witness(
        correct(),wrong(),wrong(),correct())


@pytest.mark.parametrize("bad",[
    wrong().replace("arithmetic mean","geometric mean"),
    wrong().replace("divided by 2","divided by 3"),
    wrong().replace("for constant i sub e x","for constant i sub e y"),
    wrong().replace("initial and final","initial minus final"),
    wrong().replace("no longer valid","still valid"),
    wrong().replace("constant i sub e x","constant i sub e x squared"),
    wrong().replace("for constant i sub e x","for negative i sub e x"),
    correct().replace("for constant ay sub ex","for constant vee sub ex"),
    correct().replace("for constant ay sub ex","for constant ay sub why"),
])
def test_unrelated_math_numbers_signs_axis_or_claim_never_permitted(bad):
    assert not verified_isolated_component_letter_witness(
        correct(),correct(),bad,correct())


@pytest.mark.parametrize("source",[
    correct().replace("for constant ay sub ex","for a constant acceleration"),
    correct().replace("for constant ay sub ex","for constant ay sub why"),
    correct().replace("for constant ay sub ex","for constant ay sub ex squared"),
])
def test_different_source_or_axis_is_not_eligible(source):
    assert not verified_isolated_component_letter_witness(
        source,correct(),wrong(),correct())


def test_normal_gate_asks_only_third_blind_model_and_verifies_receipt(tmp_path):
    stage=tmp_path/"private"
    text=prepare(stage)
    old_bytes=(stage/"slide1.wav").read_bytes()
    report=report_for(stage,text)
    assert report["review_required_slides"]==[1]
    seen=[]
    def third_factory(models):
        seen.append(models)
        return (lambda _: (_ for _ in ()).throw(AssertionError(
            "First model must not be called again")),
                lambda _:text,models)
    outcome=gate._bounded_independent_math_tiebreak(
        stage,[text],report,("gemini-test-3.5","gemini-test-3.8"),
        provider_factory=third_factory)
    assert seen==[("gemini-test-3.5","gemini-2.5-pro")]
    assert outcome["review_required_slides"]==[]
    assert outcome["slides"][0]["third_independent_review"]["status"]==(
        "SOURCE_BOUND_COMPONENT_LETTER_WITNESS")
    assert (stage/"slide1.wav").read_bytes()==old_bytes
    gate._verify(stage,outcome,[text])
    good,reasons=verify_acoustic_evidence(
        outcome,stage,[text],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"))
    assert good,reasons


@pytest.mark.parametrize("answer",[
    wrong(),
    wrong().replace("constant i","negative i"),
    correct().replace("divided by 2","divided by 3"),
    "",
])
def test_bad_or_empty_third_never_passes_and_does_not_mutate_pcm(tmp_path,answer):
    stage=tmp_path/"private"
    text=prepare(stage)
    before=digest_file(stage/"slide1.wav")
    calls=[]
    def factory(models):
        calls.append(models)
        return (lambda _:text,lambda _:answer,models)
    result=gate._bounded_independent_math_tiebreak(
        stage,[text],report_for(stage,text),
        ("gemini-test-3.5","gemini-test-3.8"),
        provider_factory=factory)
    assert calls==[("gemini-test-3.5","gemini-2.5-pro")]
    assert result["review_required_slides"]==[1]
    assert "third_independent_review" not in result["slides"][0]
    assert digest_file(stage/"slide1.wav")==before


@pytest.mark.parametrize("key,value",[
    ("transcript",wrong()),
    ("audio_sha256","0"*64),
    ("expected_spoken_sha256","0"*64),
    ("model","gemini-test-3.8"),
    ("status","SOURCE_BOUND_ISOLATED_DECIMAL_WITNESS"),
    ("publication_allowed",True),
])
def test_fake_witness_receipt_is_rejected_by_independent_gate(tmp_path,key,value):
    stage=tmp_path/"private"
    text=prepare(stage)
    report=gate._bounded_independent_math_tiebreak(
        stage,[text],report_for(stage,text),
        ("gemini-test-3.5","gemini-test-3.8"),
        provider_factory=lambda models:(lambda _:text,lambda _:text,models))
    changed=copy.deepcopy(report)
    changed["slides"][0]["third_independent_review"][key]=value
    good,reasons=verify_acoustic_evidence(
        changed,stage,[text],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"))
    assert not good,reasons


def hp_real_stage():
    value=os.environ.get("MICROGEN_HP_G3_COMPONENT_STAGE","")
    if not value:
        pytest.skip("source/PCM private HP fixture not enabled")
    return Path(value)


def _real_inputs():
    stage=hp_real_stage()
    textdata=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    texts=[normalize_scientific_speech(row["tts_text"])
           for row in textdata["slides"]]
    tracepath=next(stage.glob(".microgen_private_acoustic_failed_*.json"))
    trace=json.loads(tracepath.read_text(encoding="utf8"))
    assert len(texts)==21 and trace["review_required_slides"]==[6]
    return stage,texts,trace,tracepath


def test_actual_21_slide_source_wav_blind_trace_checks_without_provider():
    stage,texts,trace,tracepath=_real_inputs()
    from microgen_verified_acoustic_replay import valid_trace
    assert valid_trace(tracepath,_input_snapshot(stage,21),21,
                       tuple(trace["models"]))
    before={f.name:digest_file(f) for f in
            [stage/"source.pdf",stage/"script_tts.json",
             *[stage/f"slide{i}.wav" for i in range(1,22)]]}
    expected=[x["original_blind_transcripts"] for x in trace["slides"]]
    def rec(which):
        return lambda wav:expected[int(wav.stem.removeprefix("slide"))-1][which]
    report=audit_with_recognizer(
        stage,texts,rec(0),lambda x:x,
        independent_recognizer=rec(1),
        recognition_models=tuple(trace["models"]))
    assert report["review_required_slides"]==[6]
    assert verified_isolated_component_letter_witness(
        texts[5],*expected[5],expected[5][0])
    calls=[]
    def factory(models):
        calls.append(models)
        return (lambda _:None,lambda _:expected[5][0],models)
    revised=gate._bounded_independent_math_tiebreak(
        stage,texts,report,tuple(trace["models"]),
        provider_factory=factory)
    assert calls==[(trace["models"][0],"gemini-2.5-pro")]
    assert revised["review_required_slides"]==[]
    assert revised["slides"][5]["third_independent_review"]["status"]==(
        "SOURCE_BOUND_COMPONENT_LETTER_WITNESS")
    gate._verify(stage,revised,texts)
    assert {f.name:digest_file(f) for f in
            [stage/"source.pdf",stage/"script_tts.json",
             *[stage/f"slide{i}.wav" for i in range(1,22)]]}==before


def test_real_private_acoustic_replay_one_witness_only_in_isolated_shadow(
        tmp_path,monkeypatch):
    stage,texts,trace,tracepath=_real_inputs()
    root=tmp_path/"MicroGen_AI_Checkpoints"
    oldroot=root/"OLD_TRUE_TWO_MODEL_PRIVATE"
    newroot=root/"NEW_TEST_ONLY_SAME_SOURCE"
    old=oldroot/"2.7"
    new=newroot/"2.7"
    for dest in (old,new):
        dest.mkdir(parents=True)
        for name in ("source.pdf","script_tts.json",
                     ".microgen_tts_provenance.json",
                     "microgen_acoustic_math_transcript.py"):
            shutil.copy2(stage/name,dest/name)
        for n in range(1,22):
            shutil.copy2(stage/f"slide{n}.wav",dest/f"slide{n}.wav")
    shutil.copy2(stage/"microgen_autonomous_acoustic_gate.py",
                 old/"microgen_autonomous_acoustic_gate.py")
    shutil.copy2(Path(gate.__file__),new/"microgen_autonomous_acoustic_gate.py")
    diagnostic=next(stage.glob(".microgen_acoustic_blocked_*.json"))
    shutil.copy2(diagnostic,old/diagnostic.name)
    shutil.copy2(tracepath,old/tracepath.name)
    source_sha=digest_file(stage/"source.pdf")
    for rootdir,dest,sha in ((oldroot,old,"a"*40),
                             (newroot,new,"b"*40)):
        owner={
            "publication_authorized":False,
            "scope":{"host":"hp","source_sha256":source_sha,
                     "stop_after":"acceptance","work_root":str(rootdir),
                     "code_revision":sha}}
        (rootdir/replay.OWNER).write_text(json.dumps(owner),encoding="utf8")
        (dest/".microgen_checkpoint.json").write_text(json.dumps({
            "package_commit":sha,"completed":{"tts":"verified offline"},
        }),encoding="utf8")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setattr(replay.socket,"gethostname",lambda:"hp")
    calls=[]
    good=trace["slides"][5]["original_blind_transcripts"][0]
    def fake_provider(models):
        calls.append(models)
        return (lambda _: (_ for _ in ()).throw(AssertionError(
            "Must not re-call original reviewer")),
                lambda _:good,models)
    original_hashes={f.name:digest_file(f) for f in
                     [new/"source.pdf",new/"script_tts.json",
                      *[new/f"slide{i}.wav" for i in range(1,22)]]}
    # Test-only local reservation, no API call. Normal production reserves
    # before contacting the fresh independent Gemini third model.
    assert gate._reserve_finite_math_witness(
        new,[6],"gemini-2.5-pro",_input_snapshot(new,21))
    result=replay.maybe_replay_verified_acoustic(
        new,texts,third_provider_factory=fake_provider)
    assert result is not None
    assert calls==[(trace["models"][0],"gemini-2.5-pro")]
    assert result["evidence"]["paid_recognition_calls"]==1
    receipt={"independent_report":result["report"],
             "verified_historical_asr_reclassification":result["evidence"],
             "repaired_audio_slides":0}
    replay.verify_replay_evidence(new,receipt)
    assert {f.name:digest_file(f) for f in
            [new/"source.pdf",new/"script_tts.json",
             *[new/f"slide{i}.wav" for i in range(1,22)]]}==original_hashes
    tampered=copy.deepcopy(receipt)
    tampered["independent_report"]["slides"][5][
        "third_independent_review"]["transcript"]=(
            trace["slides"][5]["original_blind_transcripts"][1])
    with pytest.raises(replay.VerifiedAcousticReplayError):
        replay.verify_replay_evidence(new,tampered)
    # Durable reservation makes identical new-campaign third review
    # nonrepeatable even after an interruption.
    assert not gate._reserve_finite_math_witness(
        new,[6],"gemini-2.5-pro",_input_snapshot(new,21))
