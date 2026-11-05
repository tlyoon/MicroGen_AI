"""Offline regression for API-key failover in independent acoustic recognition."""
import os
from pathlib import Path
from unittest import mock

import pytest

import microgen_autonomous_acoustic_gate as gate
from microgen_tts_acoustic_qa import AcousticQAError


def test_independent_model_key_pool_recovers_and_reuses_healthy_slot():
    calls = []

    def fake_factory(key, *, model):
        def recognize(wav):
            calls.append((key, model, wav.name))
            if key == "bad":
                raise AcousticQAError("503 UNAVAILABLE")
            return f"Audible spoken words for {model}"
        return recognize

    with mock.patch.dict(os.environ, {
        "MICROGEN_GEMINI_PREFERRED_KEY_INDEX": "1",
        "MICROGEN_ACOUSTIC_MODEL_A": "model-A",
        "MICROGEN_ACOUSTIC_MODEL_B": "model-B",
    }), mock.patch("gemini_keys.get_gemini_api_keys", return_value=["bad", "good"]), \
         mock.patch.object(gate, "gemini_audio_recognizer", side_effect=fake_factory):
        first, second, model_names = gate._providers()
        assert model_names == ("model-A", "model-B")
        assert first(Path("slide1.wav")) == "Audible spoken words for model-A"
        assert first(Path("slide2.wav")) == "Audible spoken words for model-A"
        assert second(Path("slide1.wav")) == "Audible spoken words for model-B"
        assert second(Path("slide2.wav")) == "Audible spoken words for model-B"

    assert [(key, model) for key, model, _ in calls if key == "bad"] == [
        ("bad", "model-A"), ("bad", "model-B")]
    assert len([x for x in calls if x[0] == "good"]) == 4


def test_all_audio_keys_unavailable_fail_closed_in_bounded_calls():
    calls = []

    def outage_factory(key, *, model):
        def fail(wav):
            calls.append((key, model, wav.name))
            raise AcousticQAError("Unavailable")
        return fail

    with mock.patch.dict(os.environ, {
        "MICROGEN_GEMINI_PREFERRED_KEY_INDEX": "1",
        "MICROGEN_ACOUSTIC_MODEL_A": "model-A",
        "MICROGEN_ACOUSTIC_MODEL_B": "model-B",
    }), mock.patch("gemini_keys.get_gemini_api_keys", return_value=["bad", "also-bad"]), \
         mock.patch.object(gate, "gemini_audio_recognizer", side_effect=outage_factory):
        first, _, _ = gate._providers()
        with pytest.raises(gate.AutonomousAcousticError, match="configured Gemini key slots"):
            first(Path("slide1.wav"))

    assert len(calls) == 2
