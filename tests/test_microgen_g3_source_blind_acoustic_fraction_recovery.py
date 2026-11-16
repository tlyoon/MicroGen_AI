"""Bounded recurrence repair for two independent Gemini transcript formats.

These are original-ASR orthography differences, not a permissive numerical
or pronunciation policy. The routine QA entrypoint remains fail-closed.
"""
from pathlib import Path

import pytest
import microgen_tts_provenance as provenance
from microgen_acoustic_math_transcript import canonical_math_transcript
from microgen_tts_acoustic_qa import (
    mismatch_details, audit_with_recognizer,
)
from microgen_autonomous_acoustic_gate import _classify_review_blocker


@pytest.mark.parametrize("spoken,asr", [
    ("Position equals one-half times vee ex initial.",
     "Position equals 1/2 times VXI."),
    ("Velocity vee ex eff squared equals vee ex eye squared.",
     "Velocity VXF squared equals VXI squared."),
    ("Vee ex initial plus one-half ay ex times tee squared.",
     "VEX initial plus 1/2 ay ex times t squared."),
])
def test_same_visible_math_is_not_an_asr_typography_defect(spoken, asr):
    outcome = mismatch_details(spoken, asr)
    assert outcome["difference_fraction_upper_bound"] == 0, outcome
    assert outcome["sensitive_mismatches"] == 0


@pytest.mark.parametrize("spoken,wrong", [
    ("Position equals one-half times vee ex initial.",
     "Position equals 1/3 times VXI."),
    ("Position equals one-half times vee ex initial.",
     "Position equals 2/2 times VXI."),
    ("Velocity vee ex eye squared equals vee ex eff squared.",
     "Velocity VXF squared equals VXI squared."),
    ("The acceleration is minus 32 meters per second squared.",
     "The acceleration is minus 3.2 meters per second squared."),
    ("The acceleration is minus 32 meters per second squared.",
     "The acceleration is plus 32 meters per second squared."),
    ("Time is t squared.", "Time is t cubed."),
    ("One-half of the distance.", "One-third of the distance."),
    ("The second derivative changes.", "The seconds derivative changes."),
    ("The car starts 1 second after the other.",
     "The car starts 1 seconds after the other."),
])
def test_real_changed_fractions_numbers_indices_signs_or_exponents_block(spoken, wrong):
    outcome = mismatch_details(spoken, wrong)
    assert outcome["difference_fraction_upper_bound"] > 0, outcome


def test_source_blind_orthography_canonicalizer_idempotent():
    sample = "VXI plus 1/2 VXF times t is 63 meters."
    once = canonical_math_transcript(sample)
    assert canonical_math_transcript(once) == once
    for general_prose in ("There were 12 visitors.", "1/3 of the mixture.",
                          "The letter i is printed.", "The second derivative."):
        assert canonical_math_transcript(general_prose) == general_prose


@pytest.mark.parametrize("other,expected_pass", [
    ("Position equals 1/2 times VXI and time equals 2.",
     True),
    ("Position equals 1/3 times VXI and time equals 2.",
     False),
    ("Position equals 1/2 times VXF and time equals 2.",
     False),
])
def test_normal_independent_two_model_caller_reuses_fix_and_fails_closed(
        tmp_path, monkeypatch, other, expected_pass):
    # No actual provider is called, and the two model identities remain
    # distinct. This is the same normal comparison function used by G3.
    monkeypatch.setattr(provenance, "verify_manifest", lambda *args: None)
    (tmp_path/"slide1.wav").write_bytes(b"immutable_test_audio")
    (tmp_path/".microgen_tts_provenance.json").write_text("{}")
    source = "Position equals one-half times vee ex initial and time equals 2."
    result = audit_with_recognizer(
        tmp_path, [source], lambda _: source, lambda x: x,
        independent_recognizer=lambda _: other,
        recognition_models=("gemini-first", "gemini-second"),
    )
    assert (not result["review_required_slides"]) is expected_pass
    if not expected_pass:
        classification = _classify_review_blocker(result)
        assert classification["safe_auto_repair"] is False
        assert classification["root_cause_family"] in {
            "ASR_DISAGREEMENT_HOLD", "SOURCE_PRONUNCIATION_RISK_HOLD",
            "AMBIGUOUS_ACOUSTIC_EVIDENCE_HOLD",
        }
