import hashlib
import tempfile
import unittest
from pathlib import Path

from test_microgen_tts_evidence import EvidenceAdversarialTests
from microgen_tts_evidence import verify_acoustic_evidence

class SnapshotEvidenceTests(unittest.TestCase):
    def prepare(self,path):
        helper=EvidenceAdversarialTests()
        receipt,hashes,manifest=helper.baseline(path)
        receipt["schema_version"]=2
        receipt["input_snapshot_sha256"]={
            name:hashlib.sha256((path/name).read_bytes()).hexdigest()
            for name in (".microgen_tts_provenance.json","script_tts.json","slide1.wav")
        }
        return receipt,hashes,manifest
    def verify(self,p,r,hashes,manifest):
        return verify_acoustic_evidence(r,p,["The why value exists."],hashes,manifest)
    def test_v2_full_source_snapshot_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r,hashes,manifest=self.prepare(p)
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertTrue(ok,issues)
    def test_v2_source_sidecar_changed_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r,hashes,manifest=self.prepare(p)
            with (p/"script_tts.json").open("ab") as f:f.write(b" ")
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("acoustic_source_snapshot_drift:script_tts.json",issues)
    def test_v2_wrong_wave_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r,hashes,manifest=self.prepare(p)
            r["input_snapshot_sha256"]["slide1.wav"]="a"*64
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("acoustic_source_snapshot_drift:slide1.wav",issues)
    def test_missing_extra_and_unsupported_schema_fail(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r,hashes,manifest=self.prepare(p)
            del r["input_snapshot_sha256"]["script_tts.json"]
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertIn("acoustic_source_snapshot_missing_or_extra",issues)
            r["schema_version"]=3
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertIn("acoustic_schema_invalid",issues)
    def test_legacy_v1_fixtures_are_still_readable_without_v2_claim(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r,hashes,manifest=self.prepare(p)
            r["schema_version"]=1
            del r["input_snapshot_sha256"]
            ok,issues=self.verify(p,r,hashes,manifest)
            self.assertTrue(ok,issues)
