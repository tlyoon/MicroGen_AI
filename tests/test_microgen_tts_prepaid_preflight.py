import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_release_audit import setup
from microgen_tts_autonomous_campaign import (
    preflight_before_paid_recognition,run_autonomous_campaign,AutonomousCampaignError,
)

class PrepaidPreflightTests(unittest.TestCase):
    def test_valid_stage_enters_recognition_without_manual_gates(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=preflight_before_paid_recognition(stage,root/"new")
            self.assertTrue(result["prepaid_checks_passed"])
            self.assertFalse(result["manual_review_required"])
    def test_audio_corruption_prevents_any_asr_invocation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            (stage/"slide1.wav").write_bytes(b"broken")
            invoked=[]
            def record(_):invoked.append("paid");return "The why value exists."
            with self.assertRaises(Exception):
                run_autonomous_campaign(stage,root/"new",record,record,models=("A","B"))
            self.assertEqual(invoked,[])
            self.assertFalse((root/"new").exists())
    def test_video_at_limit_refuses_all_paid_recognition(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            called=[]
            def mark(_):called.append(1);return "The why value exists."
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":600}):
                with self.assertRaisesRegex(AutonomousCampaignError,"video_duration"):
                    run_autonomous_campaign(stage,root/"new",mark,mark,
                                             models=("A","B"))
            self.assertEqual(called,[])
    def test_voice_provenance_failure_blocks_even_if_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            (stage/".microgen_tts_provenance.json").unlink()
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                with self.assertRaisesRegex(AutonomousCampaignError,"voice_bound"):
                    preflight_before_paid_recognition(stage,root/"new")
    def test_preflight_never_creates_external_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                preflight_before_paid_recognition(stage,root/"new")
            self.assertFalse((root/"new").exists())
