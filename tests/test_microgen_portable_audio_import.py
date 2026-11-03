"""Synthetic PCM/WAV return path. No model, browser, source textbook or voice API."""
import array
import hashlib
import json
import math
import tempfile
import wave
from pathlib import Path

import pytest

from microgen_portable_audio_import import (
    PortableAudioImportError, make_audio_capture_template,
    audit_portable_audio_import,
)
from microgen_pronunciation_closed_loop import sha_file


def prepare(root):
    handoff = root / "voice_handoff.json"
    texts = [
        "An original synthetic teaching sentence about careful measurements.",
        "A separate synthetic narration about the reading of a graph.",
    ]
    rows = [
        {"slide": i, "topic_id": "topic_" + str(i), "source_page": i,
         "input_text": speech,
         "text_sha256": hashlib.sha256(speech.encode()).hexdigest(),
         "formal_synthesis_authorized": False,
         "audio_filename": None, "audio_sha256": None}
        for i, speech in enumerate(texts, 1)
    ]
    handoff.write_text(json.dumps({
        "status": "PORTABLE_VOICE_INPUT_READY_FORMAL_PRODUCTION_BLOCKED",
        "section_id": "B.2", "slide_count": 2,
        "publication_allowed": False,
        "formal_voice_synthesis_authorized": False,
        "formal_voice_provider": None, "formal_voice_name": None,
        "source_pdf_sha256": "a" * 64,
        "rendered_pdf_sha256": "b" * 64,
        "requests": rows,
    }))
    audio = root / "recorded"
    audio.mkdir()
    capture = make_audio_capture_template(handoff)
    capture["declared_provider"] = "Externally provided voice"
    capture["declared_voice"] = "Unverified speaker label"
    for i, entry in enumerate(capture["captured_wavs"], 1):
        wav = audio / entry["filename"]
        samples = array.array("h", [
            int(6000 * math.sin(2 * math.pi * (250 + i * 50) * j / 16000))
            for j in range(9600)])
        with wave.open(str(wav), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(samples.tobytes())
        entry["wav_sha256"] = sha_file(wav)
    manifest = root / "capture.json"
    manifest.write_text(json.dumps(capture))
    return handoff, audio, manifest


def test_pcm_handoff_accepts_unmodified_source_anchored_wav_inputs():
    with tempfile.TemporaryDirectory() as td:
        handoff, audio, capture = prepare(Path(td))
        hashes = [sha_file(p) for p in sorted(audio.glob("*.wav"))]
        report = audit_portable_audio_import(handoff, audio, capture)
        assert report["slide_count"] == 2
        assert report["provider_identity_independently_verified"] is False
        assert report["narration_words_actually_spoken_verified"] is False
        assert report["publication_allowed"] is False
        assert report["provider_calls"] == 0
        assert report["local_model_invocations"] == 0
        assert all(x["structural_pcm_quality_checks_passed"]
                   for x in report["captured_wavs"])
        assert hashes == [sha_file(p) for p in sorted(audio.glob("*.wav"))]


@pytest.mark.parametrize("fault", [
    "wrong_text", "wrong_audio_hash", "missing_audio",
    "extra_audio", "formal_approval", "edited_wav", "missing_provider"])
def test_mismatched_or_unverified_voice_capture_fails_closed(fault):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        handoff, audio, manifest = prepare(root)
        doc = json.loads(manifest.read_text())
        if fault == "wrong_text":
            doc["captured_wavs"][0]["source_text_sha256"] = "f" * 64
        elif fault == "wrong_audio_hash":
            doc["captured_wavs"][0]["wav_sha256"] = "f" * 64
        elif fault == "missing_audio":
            (audio / "slide01.wav").unlink()
        elif fault == "extra_audio":
            (audio / "slide03.wav").write_bytes(b"not a WAV")
        elif fault == "formal_approval":
            doc["formal_production_authorized"] = True
        elif fault == "edited_wav":
            with (audio / "slide01.wav").open("ab") as out:
                out.write(b"tampered")
        elif fault == "missing_provider":
            doc["declared_provider"] = None
        manifest.write_text(json.dumps(doc))
        with pytest.raises(PortableAudioImportError):
            audit_portable_audio_import(handoff, audio, manifest)


def test_capture_template_is_not_audio_or_authorization():
    with tempfile.TemporaryDirectory() as td:
        handoff, audio, manifest = prepare(Path(td))
        template = make_audio_capture_template(handoff)
        assert template["declared_provider"] is None
        assert template["declared_voice"] is None
        assert template["formal_production_authorized"] is False
        assert template["publication_allowed"] is False
        assert template["captured_wavs"][0]["wav_sha256"] is None
