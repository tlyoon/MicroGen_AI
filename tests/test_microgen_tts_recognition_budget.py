import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_release_audit import setup
from microgen_tts_recognition_budget import plan_recognition,RecognitionBudgetExceeded
from microgen_tts_autonomous_campaign import (
    run_autonomous_campaign,preflight_before_paid_recognition
)

class WorkBudgetTests(unittest.TestCase):
    def test_small_fixture_under_default_caps(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            plan=plan_recognition(stage,1)
            self.assertEqual(plan["planned_recognition_requests"],2)
            self.assertEqual(plan["planned_input_audio_seconds"],2.)
            self.assertIsNone(plan["price_estimate"])
    def test_count_cap_blocks_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            invoked=[]
            def model(_):invoked.append(1);return "The why value exists."
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                with self.assertRaises(RecognitionBudgetExceeded):
                    run_autonomous_campaign(stage,root/"qa",model,model,
                         models=("a","b"),max_requests=1)
            self.assertEqual(invoked,[])
            self.assertFalse((root/"qa").exists())
    def test_audio_time_cap_blocks_before_models(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                with self.assertRaisesRegex(RecognitionBudgetExceeded,"audio-seconds"):
                    preflight_before_paid_recognition(stage,root/"qa",
                                                     max_audio_seconds=1.99)
    def test_single_file_limit_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir();setup(stage)
            with self.assertRaisesRegex(RecognitionBudgetExceeded,"per-request"):
                plan_recognition(stage,1,max_wav_bytes=1024)
    def test_invalid_caps_and_pass_count_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for bad in (0,True,-1):
                with self.subTest(bad=bad),self.assertRaises(RecognitionBudgetExceeded):
                    plan_recognition(p,1,max_requests=bad)
            with self.assertRaises(RecognitionBudgetExceeded):
                plan_recognition(p,1,passes=1)
