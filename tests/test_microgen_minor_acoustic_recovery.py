"""Normal production acoustic recovery from 13-Nov Serway G2.

Offline tests prove narrow minor-ASR relief, bounded third Gemini blind
corroboration, source/wav hash verification and negative scientific controls.
They do NOT claim genuine model responses, subjective listening or release.
"""
import copy
import re
import wave
from pathlib import Path

import pytest

import microgen_autonomous_acoustic_gate as gate
from microgen_tts_acoustic_qa import (
    audit_with_recognizer, mismatch_details, verified_minor_asr_variation,
    verified_numeric_fragment_tiebreak, _input_snapshot,
)
from microgen_tts_evidence import verify_acoustic_evidence
from microgen_tts_provenance import make_record, write_manifest, digest_file
from text_to_speech_v25 import normalize_scientific_speech


def source_sentence():
    # Long, safe content so a *single* number/letter split falls within
    # the very narrow 9% WER budget; a changed mathematical value never does.
    return (
        "The average displacement equals 40 meters over the measured interval. "
        "This distance follows the specified graph and the recorded direction. "
        "We calculate the magnitude carefully using the same original units. "
        "Notice that the final comparison uses meters and not an invented unit. "
        "This is the complete example stated in the source narration."
    )


def faulty_transcription():
    return source_sentence().replace("40 meters", "4 t meters", 1).replace(
        "using the same", "using the same", 1).replace("uses meters", "uses m", 1)


def make_stage(path: Path, text: str):
    path.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path/"slide1.wav"),"wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0"*24000)
    spoken=normalize_scientific_speech(text)
    record=make_record(
        slide=1,path=path/"slide1.wav",text=spoken,
        provider="gemini_flash_lite_tts",key="fake-fixture-key",
        voice_name="Kore",language_code="en-US",
        speaking_rate=1.0,location="global")
    write_manifest(path,[record],[spoken])
    return spoken


def original_report(stage: Path, text: str, second: str):
    return audit_with_recognizer(
        stage,[text],lambda _:second,normalize_scientific_speech,
        independent_recognizer=lambda _:text,
        recognition_models=("fake-blind-A","fake-blind-B"))


def test_historical_slide6_minor_math_letter_typography_is_not_a_failure():
    base=("The position at t a was described using velocity vee and time tee. "
          "We proceed with the same coordinates and the original physical "
          "units in the lesson. The entire source explanation remains intact "
          "and no mathematical value has been changed. ")
    expected=base+("The lecture also includes a clear explanation of "
        "measurements and numerical comparisons without deleting anything. "*6)
    first=expected.replace("at t a was","at ta was").replace("vee","v")
    second=expected.replace("tee","t")
    assert verified_minor_asr_variation(expected,first,second)
    assert mismatch_details(first,second)["difference_fraction_upper_bound"]>0


@pytest.mark.parametrize("variant",[
    lambda s:s.replace("40 meters","50 meters",1),
    lambda s:s.replace("40 meters","4 meters",1),
    lambda s:s.replace("40 meters","40 kilometers",1),
    lambda s:s.replace("equals 40","does not equal 40",1),
    lambda s:s.replace("equals 40","minus 40",1),
    lambda s:s.replace("40 meters","40 meters squared",1),
    lambda s:s.replace("The average displacement equals 40 meters over the measured interval.",
                      "",1),
])
def test_glaring_or_unknown_math_change_never_enters_minor_recovery(variant):
    expected=source_sentence()
    heard=variant(expected)
    assert not verified_minor_asr_variation(expected,heard,expected)
    assert not verified_numeric_fragment_tiebreak(
        expected,heard,expected,expected)


def test_number_fragment_requires_third_independent_source_blind_support():
    exp=source_sentence()
    split=faulty_transcription()
    assert mismatch_details(exp,split)["sensitive_mismatches"]
    assert not verified_minor_asr_variation(exp,split,exp)
    assert verified_numeric_fragment_tiebreak(exp,split,exp,exp)
    assert not verified_numeric_fragment_tiebreak(
        exp,split,exp,split)
    assert not verified_numeric_fragment_tiebreak(
        exp,split,exp,exp.replace("40","50",1))


def test_normal_stage_witness_adjudicates_real_wav_bound_evidence(tmp_path):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    observed=original_report(stage,exp,faulty_transcription())
    assert observed["review_required_slides"]==[1]
    calls=[]
    def provider_factory(models):
        calls.append(models)
        return (lambda _:exp,lambda _:exp,models)
    checked=gate._bounded_independent_math_tiebreak(
        stage,[spoken],observed,("fake-blind-A","fake-blind-B"),
        provider_factory=provider_factory)
    assert calls==[("fake-blind-A","gemini-2.5-pro")]
    assert checked["review_required_slides"]==[]
    assert checked["slides"][0]["assessment"]==gate.PASS
    evidence=checked["slides"][0]["third_independent_review"]
    assert evidence["audio_sha256"]==digest_file(stage/"slide1.wav")
    assert evidence["model"]=="gemini-2.5-pro"
    assert checked["slides"][0]["transcripts"][0]==faulty_transcription()
    assert checked["slides"][0]["transcripts"][1]==exp
    ok,issues=verify_acoustic_evidence(
        checked,stage,[spoken],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"))
    assert ok,issues
    assert checked["publishable"] is False
    assert evidence["publication_allowed"] is False
    assert checked["independent_math_tiebreak"]["resolved_slides"]==[1]


def test_math_witness_fails_when_third_model_disagrees(tmp_path):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    original=original_report(stage,exp,faulty_transcription())
    result=gate._bounded_independent_math_tiebreak(
        stage,[spoken],original,("fake-A","fake-B"),
        provider_factory=lambda models: (
            lambda _:exp, lambda _:faulty_transcription(),models))
    assert result["review_required_slides"]==[1]
    assert "third_independent_review" not in result["slides"][0]
    assert result["independent_math_tiebreak"]["resolved_slides"]==[]


def test_math_witness_model_unavailable_is_bounded_and_not_passed(tmp_path):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    original=original_report(stage,exp,faulty_transcription())
    count=[]
    def unavailable(_):
        count.append("failed single candidate")
        raise RuntimeError("Gemini not available")
    result=gate._bounded_independent_math_tiebreak(
        stage,[spoken],original,("fake-A","fake-B"),
        provider_factory=lambda models:(lambda _:exp,unavailable,models))
    assert count==["failed single candidate"]
    assert result["review_required_slides"]==[1]
    assert "third_independent_review" not in result["slides"][0]


def test_unsafe_math_conflict_never_calls_a_third_reviewer(tmp_path):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    original=original_report(stage,exp,exp.replace("40","50",1))
    calls=[]
    result=gate._bounded_independent_math_tiebreak(
        stage,[spoken],original,("fake-A","fake-B"),
        provider_factory=lambda models:calls.append(models))
    assert result["review_required_slides"]==[1]
    assert calls==[]


@pytest.mark.parametrize("field,spoof",[
    ("audio_sha256","0"*64),
    ("expected_spoken_sha256","0"*64),
    ("model","fake-blind-A"),
    ("transcript","This is clearly not a faithful mathematical lecture."),
    ("status","FAKE_APPROVAL"),
    ("publication_allowed",True),
])
def test_tampered_source_bound_witness_fails_release_evidence(
        tmp_path,field,spoof):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    original=original_report(stage,exp,faulty_transcription())
    report=gate._bounded_independent_math_tiebreak(
        stage,[spoken],original,("fake-blind-A","fake-blind-B"),
        provider_factory=lambda models:(lambda _:exp,lambda _:exp,models))
    tampered=copy.deepcopy(report)
    tampered["slides"][0]["third_independent_review"][field]=spoof
    ok,problems=verify_acoustic_evidence(
        tampered,stage,[spoken],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"))
    assert not ok,problems


def test_third_model_approval_cannot_be_forged_by_review_status_only(
        tmp_path):
    exp=source_sentence()
    stage=tmp_path/"stage"
    spoken=make_stage(stage,exp)
    report=original_report(stage,exp,faulty_transcription())
    row=report["slides"][0]
    row["assessment"]=gate.PASS
    report["review_required_slides"]=[]
    ok,problems=verify_acoustic_evidence(
        report,stage,[spoken],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"))
    assert not ok
    assert any("mismatch" in p or "disagree" in p for p in problems)


@pytest.mark.parametrize("replacement",[
    ("40 meters","50 meters"),
    ("40 meters","40 kilometers"),
    ("equals 40","equals minus 40"),
    ("equals 40","does not equal 40"),
])
def test_strict_initial_review_blocks_single_glaring_numerical_unit_or_sign_change(
        tmp_path,replacement):
    original=source_sentence()
    stage=tmp_path/"stage"
    make_stage(stage,original)
    altered=original.replace(*replacement,1)
    report=audit_with_recognizer(
        stage,[original],lambda _:altered,normalize_scientific_speech,
        independent_recognizer=lambda _:altered,
        recognition_models=("blind-A","blind-B"))
    assert report["review_required_slides"]==[1]
    assert report["slides"][0]["assessment"]=="REVIEW_REQUIRED_PRONUNCIATION_RISK"
    assert report["slides"][0]["comparisons"][0]["sensitive_mismatches"]>=1
    assert report["publishable"] is False


def test_realistic_benign_unit_abbreviation_preserved_as_non_glaring():
    expected=source_sentence()
    actual=expected.replace("40 meters","40 m",1)
    result=mismatch_details(expected,actual)
    assert result["sensitive_mismatches"]==0
    assert result["difference_fraction_upper_bound"]>0


@pytest.mark.parametrize("word,value",[
    ("twenty","20"),("thirty","30"),("forty","40"),
    ("fifty","50"),("sixty","60"),("seventy","70"),
    ("eighty","80"),("ninety","90"),
])
def test_same_source_number_word_and_written_digit_are_equivalent(word,value):
    from microgen_tts_acoustic_qa import mismatch_details
    expected=f"The mathematical constant term is {word} units."
    heard=f"The mathematical constant term is {value} units."
    result=mismatch_details(expected,heard)
    assert result["difference_fraction_upper_bound"]==0
    assert result["sensitive_mismatches"]==0


@pytest.mark.parametrize("heard",[
    "The constant term 50, then subtract 5 multiplied by time squared",
    "The constant term 4 t, then subtract 5 multiplied by time squared",
    "The constant term 40, then add 5 multiplied by time squared",
    "The constant term 40, then subtract 5 multiplied by time cubed",
    "The constant term 40, then subtract 6 multiplied by time squared",
])
def test_numeric_voice_equivalence_does_not_waive_glaring_math_changes(heard):
    from microgen_tts_acoustic_qa import mismatch_details
    expected="The constant term forty, then subtract five multiplied by time squared"
    result=mismatch_details(expected,heard)
    assert result["difference_fraction_upper_bound"]>0
    assert result["sensitive_mismatches"]>0
    assert not verified_minor_asr_variation(
        expected+" while studying constant acceleration in this example."*4,
        heard+" while studying constant acceleration in this example."*4,
        expected+" while studying constant acceleration in this example."*4)
