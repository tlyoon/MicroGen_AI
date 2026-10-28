"""Fail-closed tests for provenance-bound mathematical TTS triage."""
import copy
import dataclasses
import hashlib

import pytest

from microgen_source_tts_provenance_triage import (
    PronunciationTriageError, assess_provenance,
)
from microgen_tts_risk_register import find_pronunciation_risks
from text_to_speech_v25 import normalize_scientific_speech


def sha(value):
    return hashlib.sha256(value.encode("utf8")).hexdigest()


def inputs(raw="A function is continuous at c. Next we examine x equals one."):
    spoken = normalize_scientific_speech(raw)
    assert spoken
    risks = [dataclasses.asdict(x) for x in find_pronunciation_risks(raw, spoken)]
    wav_sha = "a" * 64
    script = {"slides": [{"slide": 1, "tts_text": raw}]}
    risk = {
        "slide_count": 1, "publishable": False, "risk_count": len(risks),
        "slides": [{
            "slide": 1, "tts_source_sha256": sha(raw),
            "spoken_input_sha256": sha(spoken), "audio_wav_sha256": wav_sha,
            "risks": risks,
        }],
    }
    prov = {
        "slide_count": 1, "technical_provenance_verified": True,
        "listening_qa_verified": False, "academic_qa_verified": False,
        "provider": "pinned-provider", "voice_name": "pinned-voice",
        "slides": [{
            "slide": 1, "normalized_input_sha256": sha(spoken),
            "sha256": wav_sha, "provider": "pinned-provider",
            "voice_name": "pinned-voice",
        }],
    }
    return script, risk, prov, [wav_sha]


def test_math_c_has_text_normalization_not_acoustic_approval():
    raw = "At c. Next comes the limit."
    report = assess_provenance(*inputs(raw))
    assert report["by_triage"] == {"NORMALIZED_INPUT_VERIFIED_LISTENING_PENDING": 1}
    assert not report["acoustic_approval"]
    assert not report["publication_allowed"]


def test_other_math_letter_remains_unresolved():
    report = assess_provenance(*inputs("At x equals one, the function jumps."))
    assert report["by_triage"]["UNRESOLVED_LISTENING_RISK"] == 1
    assert not report["acoustic_approval"]


@pytest.mark.parametrize("change", ["spoken_hash", "wav_sha", "risk_offset", "voice",
                                    "slide_id", "false_approval"])
def test_tampering_fails_closed(change):
    script, risk, prov, hashes = copy.deepcopy(inputs())
    if change == "spoken_hash":
        prov["slides"][0]["normalized_input_sha256"] = "0" * 64
    elif change == "wav_sha":
        risk["slides"][0]["audio_wav_sha256"] = "1" * 64
    elif change == "risk_offset":
        risk["slides"][0]["risks"][0]["start"] += 1
    elif change == "voice":
        prov["slides"][0]["voice_name"] = "other-voice"
    elif change == "slide_id":
        risk["slides"][0]["slide"] = 2
    elif change == "false_approval":
        prov["listening_qa_verified"] = True
    with pytest.raises(PronunciationTriageError):
        assess_provenance(script, risk, prov, hashes)


def test_reuse_does_not_mutate_input_objects():
    args = inputs()
    before = copy.deepcopy(args)
    assess_provenance(*args)
    assert args == before


def test_unrelated_circa_not_misclassified_as_math():
    report = assess_provenance(*inputs("The illustration was painted c. 1900."))
    assert report["risk_count"] == 0
    assert report["by_triage"] == {}
