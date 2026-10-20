import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_release_audit import setup,acoustic_fixture
from microgen_tts_quality_campaign import run_qa_campaign
from microgen_tts_provenance import digest_file

class AcousticCampaignTests(unittest.TestCase):
    def test_external_real_receipt_can_clear_technical_gate_without_human(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir()
            digest=setup(stage)
            report=acoustic_fixture(stage,digest)
            old=digest_file(stage/"slide1.wav")
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=run_qa_campaign(stage,p/"qa",acoustic_report=report)
            self.assertTrue(result["acoustic_evidence_imported"])
            self.assertTrue(result["acoustic_evidence_verified"])
            self.assertTrue(result["automated_technical_qa_passed"])
            self.assertTrue(result["release_ready"])
            self.assertFalse(result["human_listening_signed"])
            self.assertFalse(result["published"])
            self.assertTrue((p/"qa"/"release_readiness_TECHNICAL_READY.json").exists())
            self.assertTrue((p/"qa"/"input_acoustic_evidence.json").exists())
            self.assertEqual(digest_file(stage/"slide1.wav"),old)
    def test_no_receipt_keeps_acoustic_gate_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir();setup(stage)
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=run_qa_campaign(stage,p/"qa")
            self.assertFalse(result["acoustic_evidence_imported"])
            self.assertFalse(result["acoustic_evidence_verified"])
            self.assertFalse(result["release_ready"])
            self.assertIn("independent_acoustic_screen",result["release_blockers"])
    def test_tampered_acoustic_receipt_cannot_clear_machine_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir()
            digest=setup(stage);receipt=acoustic_fixture(stage,digest)
            receipt["slides"][0]["expected_spoken_sha256"]="0"*64
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=run_qa_campaign(stage,p/"qa",acoustic_report=receipt)
            self.assertTrue(result["acoustic_evidence_imported"])
            self.assertFalse(result["acoustic_evidence_verified"])
            self.assertFalse(result["release_ready"])
            self.assertTrue((p/"qa"/"release_readiness_BLOCKED.json").exists())
            self.assertFalse((p/"qa"/"release_readiness_TECHNICAL_READY.json").exists())
