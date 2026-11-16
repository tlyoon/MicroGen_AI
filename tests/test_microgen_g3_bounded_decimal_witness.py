"""Independent third Gemini witness for an isolated integer/decimal ASR conflict.

No paid calls or private lecture transcripts are used in these tests.
Passing synthetic evidence cannot certify the real section 2.7 WAV.
"""
import copy
import wave

import pytest
import microgen_autonomous_acoustic_gate as gate
from microgen_tts_acoustic_qa import (
    audit_with_recognizer, verified_isolated_decimal_asr_witness,
)
from microgen_tts_evidence import verify_acoustic_evidence
from microgen_tts_provenance import make_record, write_manifest, digest_file
from text_to_speech_v25 import normalize_scientific_speech


def example():
    return (
        "The airplane starts with a measured velocity and comes to rest. "
        "The signed acceleration is minus 32 meters per second squared. "
        "This numerical value is important to the scientific conclusion. "
        "Compare the original graph with the stated result and explain "
        "the physical interpretation without changing any units or signs. "
        "Every numerical relationship must still be verified independently."
    )


def mistranscription():
    return example().replace("32 meters", "3 point 2 m", 1)


def prepare(stage):
    stage.mkdir()
    with wave.open(str(stage/"slide1.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0" * 24000)
    spoken=normalize_scientific_speech(example())
    record=make_record(
        slide=1, path=stage/"slide1.wav", text=spoken,
        provider="gemini_flash_lite_tts", key="offline-test-only",
        voice_name="Kore", language_code="en-US",
        speaking_rate=1.0, location="global",
    )
    write_manifest(stage,[record],[spoken])
    return spoken


def make_report(stage, text, bad):
    return audit_with_recognizer(
        stage,[text],lambda _:bad,normalize_scientific_speech,
        independent_recognizer=lambda _:text,
        recognition_models=("gemini-test-primary","gemini-test-independent"),
    )


def test_exact_decimal_conflict_eligible_only_with_third_blind_witness():
    good=example()
    bad=mistranscription()
    assert verified_isolated_decimal_asr_witness(good,bad,good,good)
    assert not verified_isolated_decimal_asr_witness(good,bad,good,bad)
    assert not verified_isolated_decimal_asr_witness(good,bad,bad,good)


@pytest.mark.parametrize("bad", [
    example().replace("32 meters","50 meters",1),
    example().replace("32 meters","3 point 2 kilometers",1),
    example().replace("32 meters","3 point 2 seconds",1),
    example().replace("minus 32","plus 3 point 2",1),
    example().replace("minus 32","minus 3 point 2",1).replace(
        "comes to rest","does not come to rest",1),
    example().replace("32 meters","3 point 2 m",1).replace(
        "scientific conclusion","scientific opposite",1),
    example().replace("32 meters","3 point 2 m",1).replace(
        "original graph","different graph",1),
])
def test_unsafe_alternative_number_unit_sign_or_extra_claim_remains_unresolved(bad):
    assert not verified_isolated_decimal_asr_witness(
        example(),bad,example(),example())


def test_normal_third_review_path_verifies_real_fixture_hashes_and_provenance(tmp_path):
    stage=tmp_path/"stage"
    spoken=prepare(stage)
    report=make_report(stage,spoken,mistranscription())
    assert report["review_required_slides"]==[1]
    calls=[]
    def provider_factory(models):
        calls.append(models)
        return (lambda _:spoken,lambda _:spoken,models)
    after=gate._bounded_independent_math_tiebreak(
        stage,[spoken],report,
        ("gemini-test-primary","gemini-test-independent"),
        provider_factory=provider_factory,
    )
    assert calls==[("gemini-test-primary","gemini-2.5-pro")]
    assert after["review_required_slides"]==[]
    witness=after["slides"][0]["third_independent_review"]
    assert witness["status"]=="SOURCE_BOUND_ISOLATED_DECIMAL_WITNESS"
    assert witness["audio_sha256"]==digest_file(stage/"slide1.wav")
    assert witness["publication_allowed"] is False
    assert after["publishable"] is False
    ok,reasons=verify_acoustic_evidence(
        after,stage,[spoken],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"),
    )
    assert ok,reasons


def test_bad_third_review_remains_blocked_and_preserves_original_audio(tmp_path):
    stage=tmp_path/"stage"
    spoken=prepare(stage)
    before=(stage/"slide1.wav").read_bytes()
    report=make_report(stage,spoken,mistranscription())
    calls=[]
    def factory(models):
        calls.append(models)
        return (lambda _:spoken,lambda _:mistranscription(),models)
    after=gate._bounded_independent_math_tiebreak(
        stage,[spoken],report,
        ("gemini-test-primary","gemini-test-independent"),
        provider_factory=factory,
    )
    assert len(calls)==1
    assert after["review_required_slides"]==[1]
    assert "third_independent_review" not in after["slides"][0]
    assert (stage/"slide1.wav").read_bytes()==before


@pytest.mark.parametrize("key,replacement", [
    ("transcript","The acceleration is minus 3.2."),
    ("audio_sha256","0"*64),
    ("model","gemini-test-primary"),
    ("expected_spoken_sha256","0"*64),
    ("status","SOURCE_BOUND_MATH_SPLIT_WITNESS"),
    ("publication_allowed",True),
])
def test_witness_tampering_is_rejected_by_independent_receipt_verifier(
        tmp_path,key,replacement):
    stage=tmp_path/"stage"
    spoken=prepare(stage)
    report=make_report(stage,spoken,mistranscription())
    after=gate._bounded_independent_math_tiebreak(
        stage,[spoken],report,
        ("gemini-test-primary","gemini-test-independent"),
        provider_factory=lambda models:(lambda _:spoken,lambda _:spoken,models),
    )
    changed=copy.deepcopy(after)
    changed["slides"][0]["third_independent_review"][key]=replacement
    ok,reasons=verify_acoustic_evidence(
        changed,stage,[spoken],[digest_file(stage/"slide1.wav")],
        digest_file(stage/".microgen_tts_provenance.json"),
    )
    assert not ok,reasons


def test_unauthorized_ad_hoc_stage_cannot_trigger_paid_witness(tmp_path):
    stage=tmp_path/"ad_hoc"
    spoken=prepare(stage)
    assert not gate._authorized_finite_math_witness(stage)


def test_paid_witness_reservation_survives_restart_and_never_rebills(tmp_path):
    import json
    stage=tmp_path/"private_stage"
    stage.mkdir()
    snapshot={"slide1.wav":"a"*64,"script_tts.json":"b"*64}
    assert gate._reserve_finite_math_witness(
        stage,[1],"gemini-2.5-pro",snapshot)
    saved=stage/".microgen_independent_math_witness_attempt.json"
    receipt=json.loads(saved.read_text(encoding="utf8"))
    assert receipt["status"]=="RESERVED_PAID_THIRD_REVIEWER_NO_IMPLICIT_RETRY"
    assert receipt["candidate_slides"]==[1]
    assert receipt["max_paid_third_asr_calls"]==1
    assert receipt["publication_allowed"] is False
    assert not gate._reserve_finite_math_witness(
        stage,[1],"gemini-2.5-pro",snapshot)
    assert saved.read_text(encoding="utf8")==json.dumps(
        receipt,sort_keys=True,indent=2)
    assert not gate._reserve_finite_math_witness(
        stage,[1,2,3],"gemini-2.5-pro",snapshot)
    assert not gate._reserve_finite_math_witness(
        stage,[1],"non-Gemini-model",snapshot)
    assert not gate._reserve_finite_math_witness(
        stage,[1],"gemini-2.5-pro",{"slide1.wav":"unverified"})


def test_ad_hoc_campaign_scope_never_authorizes_real_paid_review(tmp_path):
    stage=tmp_path/"work"/"2.7"
    stage.mkdir(parents=True)
    (stage/"source.pdf").write_bytes(b"synthetic-not-a-source")
    (stage/".microgen_checkpoint.json").write_text(
        '{"package_commit":"synthetic","completed":{"tts":true}}',
        encoding="utf8")
    (stage.parent/".microgen_bounded_provider_authorization.json").write_text(
        '{"schema_version":1,'
        '"status":"BOUNDED_PRIVATE_PROVIDER_SCOPE_AUTHORIZED",'
        '"publication_authorized":false,'
        '"scope":{"host":"hp","stop_after":"acceptance",'
        '"code_revision":"synthetic","work_root":"'+str(stage.parent).replace(
            chr(92),chr(92)+chr(92))+'",'
        '"source_sha256":"'+gate.digest_file(stage/"source.pdf")+'"}}',
        encoding="utf8",
    )
    # A grant-shaped file cannot authorize arbitrary external directories.
    assert not gate._authorized_finite_math_witness(stage)
