import copy
import tempfile
import unittest
from pathlib import Path

from test_microgen_tts_release_audit import setup,acoustic_fixture
from microgen_tts_evidence import verify_acoustic_evidence
import microgen_tts_release_audit as audit

class EvidenceAdversarialTests(unittest.TestCase):
    def baseline(self,stage):
        old=setup(stage)
        manifest=audit.file_hash(stage/".microgen_tts_provenance.json")
        report=acoustic_fixture(stage,old)
        return report,[old],manifest

    def verify(self,stage,report,hashes,manifest):
        return verify_acoustic_evidence(report,stage,["The why value exists."],hashes,manifest)

    def test_verified_complete_evidence_still_not_publication_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            valid,issues=self.verify(stage,report,hashes,manifest)
            self.assertTrue(valid,issues)
            self.assertFalse(report["publishable"])
    def test_identical_models_are_not_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["recognition_models"]=["same","same"]
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("acoustic_independence_unverified",issues)
    def test_transcript_must_match_declared_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["slides"][0]["transcripts"][0]="The yay value exists."
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertTrue(any("comparison_claim_drift" in x for x in issues),issues)
    def test_normalized_text_drift_blocks_even_same_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["slides"][0]["expected_spoken_sha256"]="f"*64
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("spoken_input_drift_1",issues)
    def test_false_clean_source_risk_and_summary_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["slides"][0]["assessment"]="ASR_SCREEN_PASS_LISTENING_REQUIRED"
            report["review_required_slides"]=[]
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("uncleared_source_risk_1",issues)
    def test_missing_recognizer_audio_content_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["slides"][0]["transcripts"]=["",""]
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("transcripts_missing_1",issues)
    def test_no_auto_human_signoff_in_acoustic_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            report["human_listening_approved"]=True
            ok,issues=self.verify(stage,report,hashes,manifest)
            self.assertFalse(ok)
            self.assertIn("acoustic_screen_must_not_assert_approval",issues)
    def test_sha_drift_breaks_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);report,hashes,manifest=self.baseline(stage)
            ok,issues=self.verify(stage,report,["0"*64],manifest)
            self.assertFalse(ok)
            self.assertIn("audio_drift_1",issues)
