import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import microgen_tts_autonomous_campaign as auto
from test_microgen_tts_release_audit import setup
from microgen_tts_provenance import digest_file

class UnattendedIntegrationTests(unittest.TestCase):
    def test_real_models_simulated_clear_report_progresses_without_humans(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir();setup(stage)
            before=digest_file(stage/"slide1.wav")
            transcript="The why value exists."
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=auto.run_autonomous_campaign(stage,p/"qa",lambda _:transcript,
                     lambda _:transcript,models=("fake-model-A","fake-model-B"))
            self.assertTrue(result["independent_acoustic_evidence_verified"])
            self.assertTrue(result["automated_technical_qa_passed"])
            self.assertTrue(result["ready_for_separate_promotion"])
            self.assertFalse(result["human_approval_required"])
            self.assertFalse(result["published"])
            self.assertEqual(digest_file(stage/"slide1.wav"),before)
            self.assertTrue((p/"qa"/"input_acoustic_evidence.json").is_file())
    def test_recognition_outage_never_clears_technical_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir();setup(stage)
            def outage(_):raise RuntimeError("503 offline")
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=auto.run_autonomous_campaign(stage,p/"qa",outage,outage,
                     models=("A","B"))
            self.assertFalse(result["independent_acoustic_evidence_verified"])
            self.assertFalse(result["ready_for_separate_promotion"])
            self.assertIn("independent_acoustic_screen",result["blocking_checks"])
            self.assertFalse(result["published"])
    def test_illegal_destinations_rejected_before_recognition(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir();setup(stage)
            called=[]
            def mark(_):called.append(True);return "No"
            with self.assertRaises(auto.AutonomousCampaignError):
                auto.run_autonomous_campaign(stage,stage/"qa",mark,mark)
            with self.assertRaises(auto.AutonomousCampaignError):
                auto.run_autonomous_campaign(stage,p,mark,mark)
            self.assertEqual(called,[])
    def test_invalid_model_identities_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"lesson";stage.mkdir();setup(stage)
            with self.assertRaises(ValueError):
                auto.run_autonomous_campaign(stage,p/"qa",lambda _:"okay",
                    lambda _:"okay",models=("same","same"))
            self.assertFalse((p/"qa").exists())
