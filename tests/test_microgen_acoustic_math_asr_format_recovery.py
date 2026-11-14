"""Regress 12 November real G2 dual-ASR failures without exposing private audio.

Source-blind exact mathematical transcription variants may be canonicalized.
No missing sign, exponent, numeric magnitude, reviewer hallucination, or
one-model-only recognition may be silently treated as an acoustic pass.
"""
import json
from pathlib import Path

import pytest
from google.genai import types

import microgen_autonomous_acoustic_gate as gate
from microgen_acoustic_math_transcript import canonical_math_transcript
from microgen_tts_acoustic_qa import (
    mismatch_details, tokens, is_meta_transcript,
    AUDIO_TRANSCRIPT_SCHEMA, parse_blind_audio_transcript_response,
    AcousticQAError,
)


@pytest.mark.parametrize("written,asr", [
    ("The acceleration ay ex has slope two meters per second squared.",
     "The acceleration a sub e x has slope 2 m/s2."),
    ("The velocity vee ex is positive 40 meters per second.",
     "The velocity v sub x is positive 40 m/s."),
    ("When t equals 2.0, vee ex becomes constant.",
     "When t = 2 point zero, vx becomes constant."),
    ("The acceleration ay ex avg is measured in SI units.",
     "The acceleration a y x a v g is measured in S I units."),
    ("The displacement is b t cubed minus see tee.",
     "The displacement is bt^3 - ct."),
    ("The derivative d vee ex over d t is constant.",
     "The derivative dvx over dt is constant."),
    ("The rate is positive ten meters per second squared.",
     "The rate is positive 10 m/s^2."),
    ("Each one-second interval has duration one second.",
     "Each 1-second interval has duration 1 second."),
])
def test_equivalent_exact_math_asr_notation_is_not_a_false_pronunciation_defect(
    written, asr,
):
    result=mismatch_details(written,asr)
    assert result["difference_fraction_upper_bound"]==0, result
    assert result["sensitive_mismatches"]==0


@pytest.mark.parametrize("expected,wrong", [
    ("The rate is positive 40 m/s.", "The rate is negative 40 m/s."),
    ("The rate is minus 10 m/s2.", "The rate is plus 10 m/s2."),
    ("The rate is 40 m/s2.", "The rate is 40 m/s."),
    ("The value is 2.0 s.", "The value is 2.5 s."),
    ("The number is eight point two.", "The number is eight two."),
    ("The derivative is d x squared.", "The derivative is d x cubed."),
    ("The position is b t cubed minus see t.",
     "The position is b t cubed plus see t."),
    ("We measured zero acceleration.", "We measured one acceleration."),
    ("The interpretation is continuous.", "The interpretation is discontinuous."),
    ("The name is see.", "The name is circa."),
])
def test_wrong_science_still_disagrees(expected,wrong):
    diff=mismatch_details(expected,wrong)
    assert diff["difference_fraction_upper_bound"]>0, diff


def test_source_blind_canonicalization_is_idempotent_and_unchanged_in_prose():
    raw="We visited a hospital for a CT scan and used a one-second interval."
    assert canonical_math_transcript(raw)==raw
    for sample in (
        "The acceleration a sub e x has magnitude 5 m/s2.",
        "At t = 2.0, b t cubed - ct is positive.",
        "The integral has a positive sign.",
    ):
        once=canonical_math_transcript(sample)
        assert canonical_math_transcript(once)==once


def test_reviewers_must_not_return_model_working_notes_as_transcripts():
    polluted=('x avg". Let\'s write it as "a x avg". '
              "Wait, at time t f -> t f. Let's check if there's any other word.")
    assert is_meta_transcript(polluted)
    assert not is_meta_transcript("Let us check our understanding of acceleration.")
    assert not is_meta_transcript(
        "The term instantaneous velocity is calculated using calculus.")
    with pytest.raises(AcousticQAError,match="explanatory"):
        parse_blind_audio_transcript_response(
            json.dumps({"transcript":polluted}))
    with pytest.raises(AcousticQAError,match="JSON"):
        parse_blind_audio_transcript_response("The answer is probably 40.")


def test_strict_audio_transcript_schema_accepted_by_installed_gemini_sdk():
    config=types.GenerateContentConfig(
        temperature=0, response_mime_type="application/json",
        response_json_schema=AUDIO_TRANSCRIPT_SCHEMA,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
        max_output_tokens=2400)
    assert config.response_json_schema["required"]==["transcript"]
    assert parse_blind_audio_transcript_response(
        '{"transcript": "The velocity changes with time."}')==(
        "The velocity changes with time.")


@pytest.mark.parametrize("valid_second", [True,False])
def test_normal_pipeline_rechecks_malformed_review_only_once_without_rewriting_wav(
    tmp_path,monkeypatch,valid_second,
):
    stage=tmp_path/"stage"
    stage.mkdir()
    wav=stage/"slide1.wav"
    wav.write_bytes(b"IMMUTABLE_PCM_EVIDENCE")
    before=wav.read_bytes()
    expected="The velocity changes with time and the acceleration is constant."
    notes="Let's write it as the velocity. Wait, at time t f -> t f."
    called=[0,0]
    def primary(path):
        called[0]+=1
        return expected
    def secondary(path):
        called[1]+=1
        return expected if valid_second and called[1]==2 else notes
    def offline_audit(_stage,_texts,rec1,_normalizer, *,
                      independent_recognizer,recognition_models):
        return {"transcripts":[rec1(wav),independent_recognizer(wav)],
                "recognition_models":recognition_models}
    monkeypatch.setattr(gate,"audit_with_recognizer",offline_audit)
    result=gate._transcripts(stage,[expected],(primary,secondary),
                             ("gemini-a","gemini-b"),memo={})
    assert called==[1,2]
    assert result["transcripts"][0]==expected
    assert result["transcripts"][1]==(
        expected if valid_second else notes)
    assert wav.read_bytes()==before


def test_signed_math_operators_are_never_lost_by_tokenization():
    assert mismatch_details("t minus 5","t-5")[
        "difference_fraction_upper_bound"] == 0
    assert mismatch_details("x minus y","x-y")[
        "difference_fraction_upper_bound"] == 0
    assert mismatch_details("t plus 5","t-5")[
        "difference_fraction_upper_bound"] > 0
    assert mismatch_details("x plus y","x-y")[
        "difference_fraction_upper_bound"] > 0


def test_acoustic_fingerprint_tracks_formatter_without_invalidation_of_tts(
    tmp_path,
):
    from microgen_quality import dependency_fingerprint
    for name in (
        "script_tts.json", "text_to_speech_v25.py",
        "microgen_autonomous_acoustic_gate.py", "microgen_tts_acoustic_qa.py",
        "microgen_tts_evidence.py", ".microgen_tts_provenance.json",
        "microgen_acoustic_math_transcript.py", "slide1.wav",
    ):
        (tmp_path/name).write_bytes(name.encode())
    tts_before=dependency_fingerprint(tmp_path,"tts")
    acoustic_before=dependency_fingerprint(tmp_path,"acoustic_qa")
    (tmp_path/"microgen_acoustic_math_transcript.py").write_bytes(b"UPDATED")
    assert dependency_fingerprint(tmp_path,"tts")==tts_before
    assert dependency_fingerprint(tmp_path,"acoustic_qa")!=acoustic_before


def test_standalone_tee_is_never_automatically_equated_to_time_t():
    # Preserve the prior source-grounded pronunciation safeguard.
    assert mismatch_details(
        "The t variable is positive.",
        "The tee variable is positive.")["difference_fraction_upper_bound"] > 0
    assert mismatch_details(
        "The tee of a golf ball is visible.",
        "The t of a golf ball is visible.")["difference_fraction_upper_bound"] > 0
    # But an explicitly named mathematical time variable may be written
    # differently by independent recognition models.
    assert mismatch_details(
        "The slope on the ex versus tee graph is constant.",
        "The slope on the x versus t graph is constant.")[
            "difference_fraction_upper_bound"] == 0
