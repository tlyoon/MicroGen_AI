"""V6 normal-path deterministic historical-Gemini voice clarity.

No source PDF, copyrighted transcript, provider keys or WAVs in fixtures.
Tests use synthetic mathematical speech and real immutable source is tested
separately in the owner's private HP checkpoint shadow.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

import microgen_source_bound_voice_recovery as recovery
from microgen_reviewed_math_voice import (
    reviewed_math_voice, voice_input_risk_status,
)
from text_to_speech_v25 import normalize_scientific_speech
from microgen_cue_semantic_mapping import numbers


@pytest.mark.parametrize("source,expected",[
    ("velocity vee ex initial equals vee ex final",
     "initial velocity along the x axis equals the final x component of velocity"),
    ("ay ex avg and ay ex", "the average x component of acceleration and the x component of acceleration"),
    ("vee ex car plus vee ex trooper",
     "the car's x component of velocity plus the trooper's x component of velocity"),
    ("dee vee ex over dee tee is acceleration ay ex",
     "the time derivative of the x component of velocity is acceleration along the x axis"),
])
def test_x_component_exact_speech_repair_is_fixedpoint(source,expected):
    result=recovery.clarify_x_component(source)
    assert result==expected
    assert recovery.clarify_x_component(result)==result
    assert numbers(result)==numbers(source)
    normalized=normalize_scientific_speech(result)
    assert reviewed_math_voice(normalized)==normalized
    assert voice_input_risk_status(normalized,normalize_scientific_speech)[
        "unresolved_source_risk_count"]==0


@pytest.mark.parametrize("source",[
    "Acceleration ay why equals plus 3.",
    "The mathematical function v of x at time t.",
    "The y component of velocity is zero.",
    "The force vector has a_y as its coordinate.",
    "Minus 32 meters per second squared is not minus 3.2.",
    "Graph panel E is different from panel I.",
    "The car is moving in two dimensions.",
    "Vee says ex is a letter.",
])
def test_no_guessing_y_components_sign_values_or_unrelated_english(source):
    assert recovery.clarify_x_component(source)==source


@pytest.mark.parametrize("before,after",[
    ("The acceleration ay ex equals minus 32.",
     "The acceleration along the x axis equals minus 32."),
    ("The velocity vee ex equals plus 3.2 meters per second.",
     "The velocity along the x axis equals plus 3.2 meters per second."),
])
def test_signed_magnitudes_survive_exact_component_clarity(before,after):
    assert recovery.clarify_x_component(before)==after
    assert numbers(before)==numbers(after)


def test_private_recovery_abstains_without_independent_prior_source_evidence(
        tmp_path,monkeypatch):
    stage=tmp_path/"2.7"
    stage.mkdir()
    (stage/"script_tts.json").write_text(json.dumps({
        "slides":[
            {"slide":1,"tts_text":"The velocity vee ex equals 3.",
             "narration":"The velocity vee ex equals 3."},
            {"slide":2,"tts_text":"The acceleration ay ex equals 0.",
             "narration":"The acceleration ay ex equals 0."},
        ]
    }),encoding="utf8")
    monkeypatch.setattr(recovery,"_source_bound_blind_evidence",
                        lambda stage,texts:None)
    result=recovery.recover_disputed_component_voice(stage)
    assert result["status"]=="NO_VERIFIED_HISTORICAL_ASR_VOICE_ABSTAINED"
    assert result["changed_slides"]==[]
    assert not (stage/recovery.RECEIPT).exists()
    assert not (stage/recovery.ORIGINAL).exists()


def test_crash_after_prepared_receipt_resumes_without_repeated_provider_calls(
        tmp_path):
    stage=tmp_path/"2.7"
    stage.mkdir()
    original='{"slides":[{"slide":1,"tts_text":"a"}]}'
    repaired='{"slides":[{"slide":1,"tts_text":"b"}]}'
    (stage/"source.pdf").write_bytes(b"synthetic private source")
    (stage/"script_tts.json").write_text(original,encoding="utf8")
    shutil.copy2(stage/"script_tts.json",stage/recovery.ORIGINAL)
    (stage/recovery.PROPOSAL).write_bytes(repaired.encode("utf8"))
    policy=Path(recovery.__file__)
    shutil.copy2(policy,stage/policy.name)
    row={
        "schema_version":1,
        "status":"PREPARED",
        "source_sha256":recovery.sha(stage/"source.pdf"),
        "original_sidecar_sha256":recovery.sha(stage/recovery.ORIGINAL),
        "repaired_sidecar_sha256":hashlib.sha256(repaired.encode()).hexdigest(),
        "policy_sha256":recovery.sha(stage/policy.name),
        "changed_slides":[1],
        "paid_model_calls":0,
        "publication_allowed":False,
    }
    (stage/recovery.RECEIPT).write_text(
        json.dumps(row),encoding="utf8")
    assert recovery.verify_source_voice_recovery(stage)["status"]==(
        "RECOVERED_SOURCE_BOUND_SPEECH")
    assert (stage/"script_tts.json").read_text(encoding="utf8")==repaired
    assert not (stage/recovery.PROPOSAL).exists()
    assert recovery.verify_source_voice_recovery(stage)["restarted"]
    (stage/"script_tts.json").write_text("UNTRUSTED ALTERATION",encoding="utf8")
    with pytest.raises(recovery.SourceBoundVoiceRecoveryError,
                       match="changed"):
        recovery.verify_source_voice_recovery(stage)


def test_unjournaled_modified_audio_source_never_passes_narration_gate(
        tmp_path):
    stage=tmp_path/"2.7"
    stage.mkdir()
    (stage/recovery.ORIGINAL).write_text("old",encoding="utf8")
    (stage/"script_tts.json").write_text("changed",encoding="utf8")
    with pytest.raises(recovery.SourceBoundVoiceRecoveryError,
                       match="Unjournaled"):
        recovery.verify_source_voice_recovery(stage)


def test_exact_math_recovery_policy_is_in_source_bound_voice_hash():
    from microgen_reviewed_math_voice import voice_adapter_code_sha256
    import inspect
    source=inspect.getsource(voice_adapter_code_sha256)
    assert "microgen_source_bound_voice_recovery.py" in source
    assert len(voice_adapter_code_sha256())==64


def test_normal_narration_stage_refuses_unverified_voice_transaction(
        tmp_path,monkeypatch):
    import microgen_batch as batch
    stage=tmp_path/"2.7"
    stage.mkdir()
    monkeypatch.setattr(batch.quality,"check_slide_pdf",
                        lambda *a,**k:{"pages":21})
    monkeypatch.setattr(batch.quality,"check_narration",
                        lambda *a,**k:{"pages":21})
    monkeypatch.setattr(
        recovery,"verify_source_voice_recovery",
        lambda stage: (_ for _ in ()).throw(
            recovery.SourceBoundVoiceRecoveryError("source voice SHA drift")
        ),
    )
    assert batch.stage_valid(stage,"narration",tmp_path/"NEVER_PUBLISH") is False


def test_no_receipt_but_prepared_old_sidecar_can_recover_without_any_provider(
        tmp_path,monkeypatch):
    stage=tmp_path/"2.7"
    stage.mkdir()
    payload=b'{"slides":[{"slide":1,"tts_text":"ay ex"}, {"slide":2,"tts_text":"vee ex"}]}'
    (stage/"script_tts.json").write_bytes(payload)
    (stage/recovery.ORIGINAL).write_bytes(payload)
    (stage/recovery.PROPOSAL).write_bytes(b"UNCOMMITTED")
    monkeypatch.setattr(recovery,"_source_bound_blind_evidence",
                        lambda stage,texts:None)
    result=recovery.recover_disputed_component_voice(stage)
    assert result["status"]=="NO_VERIFIED_HISTORICAL_ASR_VOICE_ABSTAINED"
    assert not (stage/recovery.ORIGINAL).exists()
    assert not (stage/recovery.PROPOSAL).exists()
    assert (stage/"script_tts.json").read_bytes()==payload


def test_original_scientific_script_remains_untouched_by_source_voice_policy():
    import inspect
    from microgen_source_bound_voice_recovery import (
        recover_disputed_component_voice,
    )
    source=inspect.getsource(recover_disputed_component_voice)
    assert 'row["tts_text"]=repaired' in source
    assert 'row["narration"]=' not in source
    assert '_require_budget_preflight' in source
    assert 'semantic_limit=MAX_SEMANTIC_SLIDES' in source
    assert 'preflight_voice_sidecar(candidate,require_policy_binding=True)' in source

@pytest.mark.parametrize("before,expected",[
    (
        "a jet lands with an initial velocity vee ex eye of approximately 63 "
        "meters per second",
        "a jet lands with an initial velocity along the x axis of approximately "
        "63 meters per second",
    ),
    (
        "the jet has final velocity vee ex eff at the end",
        "the jet has final velocity along the x axis at the end",
    ),
    (
        "a car passes a billboard at constant speed vee ex car of 45.0 meters per second",
        "a car passes a billboard at a constant velocity along the x axis of 45.0 meters per second",
    ),
    (
        "under constant ay ex and the vee ex graph",
        "under constant acceleration along the x axis and the x component of velocity graph",
    ),
    (
        "vee sub ex average equals vee sub ex initial",
        "the average x component of velocity equals the initial x component of velocity",
    ),
])
def test_contextual_component_clarity_no_repeated_words_or_split_cues(before,expected):
    output=recovery.clarify_x_component(before)
    assert output==expected
    assert recovery.clarify_x_component(output)==output
    assert numbers(before)==numbers(output)
    normalized=normalize_scientific_speech(output)
    for defect in ("initial initial", "final final", "the the",
                   "constant the", "speed the car's"):
        assert defect not in normalized

def test_source_bound_car_velocity_phrase_clears_real_pronunciation_risk():
    before=(
        "A car passes a billboard at constant speed vee ex car of "
        "45.0 meters per second."
    )
    revised=normalize_scientific_speech(
        recovery.clarify_x_component(before)
    )
    assert revised==(
        "A car passes a billboard at a constant velocity along the "
        "ex axis of 45.0 meters per second."
    )
    assert numbers(before)==numbers(revised)
    assert voice_input_risk_status(
        revised,normalize_scientific_speech
    )["unresolved_source_risk_count"]==0
    assert "x-direction" not in revised
    assert recovery.clarify_x_component(revised)==revised

def test_displacement_parentheses_voice_keeps_exact_source_equation():
    from microgen_reviewed_math_voice import reviewed_math_voice
    before=("The final ex component of velocity squared equals the initial "
            "ex component of velocity squared plus 2 the ex component of "
            "acceleration times ex final minus ex initial.")
    result=reviewed_math_voice(before)
    assert result==(before.replace(
        "times ex final minus ex initial",
        "times the quantity ex final minus ex initial"))
    assert reviewed_math_voice(result)==result
    assert numbers(result)==numbers(before)
    for changed in (
        before.replace("minus ex initial","plus ex initial"),
        before.replace("ex final minus ex initial","ex initial minus ex final"),
        before.replace("times ex final","times why final"),
        before.replace("acceleration times","velocity times"),
    ):
        assert reviewed_math_voice(changed)==changed

def test_real_failure_family_compact_x_component_voice_is_source_faithful():
    from microgen_reviewed_math_voice import reviewed_math_voice
    before=("The velocity vee sub ex final equals vee sub ex initial "
            "plus ay sub ex times t. The jet has acceleration ay sub ex.")
    # A complete, potentially ambiguous equation role triggers pronunciation
    # clarification even in a fresh production run, not just a prior PDF.
    after=reviewed_math_voice(before)
    assert "final velocity along the x axis equals" in after
    assert "the initial x component of velocity" in after
    assert "the x component of acceleration" in after
    assert "ay sub ex" not in after
    assert numbers(after)==numbers(before)
    assert reviewed_math_voice(after)==after


def test_previously_clear_average_velocity_narration_not_unnecessarily_revoiced():
    from microgen_reviewed_math_voice import reviewed_math_voice
    source=("Let us examine Average Velocity for Constant Acceleration. "
            "vee sub ex average equals vee sub ex initial plus vee sub ex final, "
            "divided by 2, for constant ay sub ex.")
    assert reviewed_math_voice(source)==source


def test_full_integer_fraction_voice_changes_neither_value_nor_sign():
    from microgen_reviewed_math_voice import reviewed_math_voice
    before=("Calculating acceleration gives 0 minus 63 divided by 2.0, "
            "yielding minus 32 meters per second squared.")
    after=reviewed_math_voice(before)
    assert "the whole-number value 63" in after
    assert "that entire numerator divided by 2.0" in after
    assert "minus 32" in after
    assert "6.3" not in after
    assert numbers(before)==numbers(after)
    assert reviewed_math_voice(after)==after
    wrong=before.replace("63","6.3")
    assert "whole-number value" not in reviewed_math_voice(wrong)


def test_source_voice_preserves_mathematically_different_axis_or_operator():
    from microgen_reviewed_math_voice import reviewed_math_voice
    wrong=("The y component of acceleration is negative, "
           "and ex final plus ex initial equals 63.")
    assert reviewed_math_voice(wrong)==wrong
    from microgen_tts_acoustic_qa import mismatch_details
    assert mismatch_details("The number is 63.","The number is 6.3.")[
        "sensitive_mismatches"]>0
    assert mismatch_details("ay ex is positive","a sub y is positive")[
        "difference_fraction_upper_bound"]>0

def test_quadratic_minus_sign_clarity_without_operator_loss():
    from microgen_reviewed_math_voice import reviewed_math_voice
    source=("The quadratic equation one-half ay sub ex times tee squared "
            "minus vee ex car times t minus ex bee equals 0.")
    spoken=reviewed_math_voice(source)
    assert "minus the full product of the car's x component of velocity" in spoken
    assert "minus the position term ex bee equals 0" in spoken
    assert spoken.count("minus") == 2
    assert numbers(source)==numbers(spoken)
    assert reviewed_math_voice(spoken)==spoken
    for altered in (
        source.replace("minus vee ex car", "plus vee ex car"),
        source.replace("minus ex bee", "plus ex bee"),
        source.replace("tee squared", "tee cubed"),
    ):
        assert "minus the full product" not in reviewed_math_voice(altered)

def test_narrator_keeps_complete_signed_integer_division_in_one_cue():
    from microgen_reviewed_math_voice import reviewed_math_voice
    source=("Calculating ay ex equals the fraction v ex final minus vee "
            "ex eye over t gives 0 minus 63 divided by 2.0, yielding "
            "minus 32 meters per second squared.")
    voice=reviewed_math_voice(source)
    assert ("the whole-number value 63 with that entire numerator "
            "divided by 2.0, yielding") in voice
    assert "the whole-number value 6.3" not in voice
    assert numbers(voice)==numbers(source)
    assert reviewed_math_voice(voice)==voice
    for changed in (
        source.replace("0 minus 63","0 plus 63"),
        source.replace("63 divided","6.3 divided"),
        source.replace("divided by 2.0","divided by 0"),
    ):
        assert "whole-number value 63" not in reviewed_math_voice(changed)

def test_recurrent_compact_x_acceleration_blind_asr_is_prevented_before_tts():
    from microgen_reviewed_math_voice import reviewed_math_voice
    examples={
        "The straight line has constant slope equal to the acceleration ay ex.":
        "constant slope equal to the acceleration along the x axis.",
        "instantaneous acceleration defined as ay ex equals dee vee sub ex over dee tee":
        "defined as the x component of acceleration equals",
        "Constant acceleration means ay ex equals ay sub ex average":
        "means the x component of acceleration equals the average x component of acceleration",
        "Finally, when ay ex equals 0, all equations reduce to constant velocity.":
        "when the x component of acceleration equals 0",
    }
    for before,required in examples.items():
        after=reviewed_math_voice(before)
        assert required in after,(before,after)
        assert numbers(after)==numbers(before)
        assert reviewed_math_voice(after)==after

    # This older compact symbol has an established reviewed pronunciation.
    assert reviewed_math_voice(
        "Later, a sub x equals zero.")=="Later, ay sub ex equals zero."
    for unreviewed in (
        "The acceleration is in the y direction.",
        "A colloquial remark about a y-shaped axis.",
        "The symbol ay ex is an arbitrary variable name.",
        "For a 2D problem, ay equals positive acceleration.",
    ):
        assert reviewed_math_voice(unreviewed)==unreviewed

    wrong="The straight line has constant slope equal to the acceleration ay why."
    assert reviewed_math_voice(wrong)==wrong
