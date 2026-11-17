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
        "a car passes a billboard at a constant x-direction speed of 45.0 meters per second",
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
