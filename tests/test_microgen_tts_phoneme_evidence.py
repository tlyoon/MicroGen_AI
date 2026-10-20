import json,tempfile,unittest
from pathlib import Path
from test_microgen_tts_targeted_phoneme import ScopedPhonemeTests
from microgen_tts_targeted_phoneme import scan_stage
from microgen_tts_phoneme_evidence import verify_scan,TargetedEvidenceError

class CrosscheckTests(unittest.TestCase):
    def sample(self,root):
        stage,bench,ref,judge=ScopedPhonemeTests().fixture(root)
        report=scan_stage(stage,ref,bench,judge,judge,models=("A","B"))
        return stage,bench,ref,report
    def test_valid_sha_bound_calibrated_result(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);stage,bench,ref,report=self.sample(r)
            self.assertTrue(verify_scan(stage,ref,bench,report)["technically_cleared"])
    def test_tampered_model_label_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);stage,bench,ref,report=self.sample(r)
            report["probe_rows"][0]["judgments"][0]["label"]="YAY"
            with self.assertRaisesRegex(TargetedEvidenceError,"falsified"):
                verify_scan(stage,ref,bench,report)
    def test_source_narration_drift_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);stage,bench,ref,report=self.sample(r)
            script=stage/"script_tts.json";obj=json.loads(script.read_text())
            obj["slides"][0]["tts_text"]="No variables."
            script.write_text(json.dumps(obj))
            with self.assertRaises(TargetedEvidenceError):
                verify_scan(stage,ref,bench,report)
    def test_changed_wave_and_reference_detected(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);stage,bench,ref,report=self.sample(r)
            (stage/"slide1.wav").write_bytes(b"new bytes")
            with self.assertRaises(TargetedEvidenceError):
                verify_scan(stage,ref,bench,report)
    def test_unqualified_pair_cannot_fake_success(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);stage,bench,ref,judge=self.sample(r)[:3]+(lambda *_:"UNKNOWN",)
            report=scan_stage(stage,ref,bench,judge,judge,models=("A","B"))
            self.assertFalse(verify_scan(stage,ref,bench,report)["technically_cleared"])
            report["blocked"]=False
            with self.assertRaises(TargetedEvidenceError):
                verify_scan(stage,ref,bench,report)
