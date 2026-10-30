"""Offline recorded Cloud c-dot comparison must not claim phonetic certification."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from microgen_cloud_tts_pair_audit import audit_pair, CloudTTSPairAuditError
from microgen_tts_provenance import wav_characteristics
from text_to_speech_v25 import normalize_scientific_speech

TEXT = "Evaluate at c. Next, take the limit."


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def create_one(root, *, mode, text, name):
    folder = root / name
    folder.mkdir()
    wav = folder / "diagnostic_cloud_tts_NOT_FORMAL.wav"
    with wave.open(str(wav), "wb") as dest:
        dest.setnchannels(1)
        dest.setsampwidth(2)
        dest.setframerate(24000)
        dest.writeframes(b"\x01\x00" * 6000)
    manifest = {
        "purpose": "CLOUD_TTS_TROUBLESHOOTING_ONLY_NOT_FORMAL",
        "provider": "google_cloud_chirp3",
        "voice_name": "en-US-Chirp-HD-F",
        "language": "en-US",
        "requested_characters": len(text),
        "requested_utterance_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "wav_sha256": digest(wav),
        "audio": wav_characteristics(wav),
        "synthesis_mode": mode,
        "normalization_applied": mode != "RAW_C_DOT_CONTROL_ONLY",
        "attempted_api_calls_maximum": 1,
        "chargeable_request_explicitly_confirmed": True,
        "publication_allowed": False,
        "formal_tts_manifest_created": False,
        "formal_tts_default_changed_to_cloud": False,
    }
    (folder / "diagnostic_receipt.json").write_text(json.dumps(manifest))
    return folder


def fixture(root):
    raw = create_one(root, mode="RAW_C_DOT_CONTROL_ONLY", text=TEXT, name="raw_diagnostic")
    norm = create_one(root, mode="NORMALIZED_SCIENTIFIC_SPEECH",
                      text=normalize_scientific_speech(TEXT), name="normalized_diagnostic")
    items = []
    for name,folder,heard in (
        ("literal",raw,["evaluate","at","circa","next","take","the","limit"]),
        ("normalized",norm,["evaluate","at","sea","next","take","the","limit"])):
        sha = json.loads((folder/"diagnostic_receipt.json").read_text())["wav_sha256"]
        items.append({
            "label": name, "receipt_wav_sha256": sha,
            "recognition": {
                "source_wav_sha256": sha,
                "words": [{"word": w} for w in heard],
                "phonetic_identity_verified": False,
                "semantic_word_alignment_certified": False,
            }
        })
    asr = root / "screen.json"
    asr.write_text(json.dumps({"items":items,"publication_allowed":False}))
    return raw,norm,asr


class DiagnosticPairTests(unittest.TestCase):
    def test_valid_pair_screen_is_not_phonetic_certification(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr = fixture(Path(path))
            result=audit_pair(raw,norm,TEXT,asr_report=asr)
            self.assertEqual(result["status"],
                "RECORDED_C_DOT_CLOUD_TTS_PAIR_AUDITED_NOT_PHONETIC_CERTIFICATION")
            self.assertEqual(result["voice_name"],"en-US-Chirp-HD-F")
            self.assertTrue(result["asr_screening_supports_normalization"])
            self.assertTrue(result["asr_raw_circa"])
            self.assertTrue(result["asr_normalized_see_like"])
            self.assertFalse(result["phonetic_identity_verified"])
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["formal_tts_default_changed"])

    def test_missing_screen_does_not_imply_phonetic_clearance(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,_ = fixture(Path(path))
            data=audit_pair(raw,norm,TEXT)
            self.assertFalse(data["asr_screening_available"])
            self.assertFalse(data["phonetic_identity_verified"])

    def test_tampered_wav_or_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr = fixture(Path(path))
            wav=raw/"diagnostic_cloud_tts_NOT_FORMAL.wav"
            wav.write_bytes(wav.read_bytes()+b"tampered")
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,TEXT,asr_report=asr)

    def test_voice_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr=fixture(Path(path))
            receipt=norm/"diagnostic_receipt.json"
            obj=json.loads(receipt.read_text());obj["voice_name"]="Microsoft Zira Desktop"
            receipt.write_text(json.dumps(obj))
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,TEXT,asr_report=asr)

    def test_mislabeled_normalization_fails(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr=fixture(Path(path))
            receipt=norm/"diagnostic_receipt.json"
            obj=json.loads(receipt.read_text());obj["normalization_applied"]=False
            receipt.write_text(json.dumps(obj))
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,TEXT,asr_report=asr)

    def test_wrong_text_and_same_source_folder_fail(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,_=fixture(Path(path))
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,"Evaluate at c. Next, do something else.")
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,raw,TEXT)

    def test_asr_hash_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr=fixture(Path(path))
            j=json.loads(asr.read_text())
            j["items"][0]["recognition"]["source_wav_sha256"]="0"*64
            asr.write_text(json.dumps(j))
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,TEXT,asr_report=asr)

    def test_false_asr_confidence_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            raw,norm,asr=fixture(Path(path))
            j=json.loads(asr.read_text())
            j["items"][1]["recognition"]["phonetic_identity_verified"]=True
            asr.write_text(json.dumps(j))
            with self.assertRaises(CloudTTSPairAuditError):
                audit_pair(raw,norm,TEXT,asr_report=asr)


if __name__=="__main__":
    unittest.main()
