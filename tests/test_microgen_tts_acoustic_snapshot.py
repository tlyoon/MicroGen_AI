import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_acoustic_qa as a
from text_to_speech_v25 import normalize_scientific_speech as normalize
from test_microgen_tts_acoustic_qa import build_verified

class AtomicAcousticSnapshotTests(unittest.TestCase):
    def test_normal_audio_creates_matching_input_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);raw=["The theorem explains continuity."]
            build_verified(stage,raw)
            (stage/"script_tts.json").write_text(json.dumps({"slides":[{"slide":1,"tts_text":raw[0]}]}))
            result=a.audit_with_recognizer(stage,raw,lambda w:raw[0],normalize,
                      independent_recognizer=lambda w:raw[0])
            self.assertIn("slide1.wav",result["input_snapshot_sha256"])
            self.assertIn("script_tts.json",result["input_snapshot_sha256"])
            self.assertEqual(result["input_snapshot_sha256"]["slide1.wav"],a.sha256(stage/"slide1.wav"))
    def test_recognizer_mutating_wave_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);raw=["The function is continuous."]
            build_verified(stage,raw)
            def malicious(wav):
                with wav.open("ab") as f:f.write(b"changed-during-acoustic-test")
                return raw[0]
            with self.assertRaisesRegex(a.AcousticQAError,"changed during recognition"):
                a.audit_with_recognizer(stage,raw,malicious,normalize,
                         independent_recognizer=lambda w:raw[0])
    def test_recognizer_mutating_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);raw=["The function is continuous."]
            build_verified(stage,raw)
            def tamper(_):
                manifest=stage/".microgen_tts_provenance.json"
                manifest.write_bytes(manifest.read_bytes()+b" ")
                return raw[0]
            with self.assertRaisesRegex(a.AcousticQAError,"changed during recognition"):
                a.audit_with_recognizer(stage,raw,tamper,normalize,
                         independent_recognizer=lambda w:raw[0])
    def test_recognizer_mutating_sidecar_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);raw=["The function is continuous."]
            build_verified(stage,raw)
            script=stage/"script_tts.json";script.write_text('{"slides":[]}')
            def tamper(_):
                script.write_text('{"slides":[{"slide":1}]}')
                return raw[0]
            with self.assertRaisesRegex(a.AcousticQAError,"changed during recognition"):
                a.audit_with_recognizer(stage,raw,tamper,normalize,
                         independent_recognizer=lambda w:raw[0])
