import hashlib
import tempfile
import unittest
from pathlib import Path
from test_microgen_tts_acoustic_benchmark import manifest
from microgen_tts_acoustic_benchmark import run_dual_model_benchmark
from microgen_tts_model_calibration import check_model_calibration,ModelCalibrationError

class CalibrationTests(unittest.TestCase):
    def prepare(self,root,wrong=False):
        samples=manifest(root)
        def fake(p):
            if wrong:return "y-value and y-value"
            return "yay value and yay value" if p.name=="before.wav" else "why value and why value"
        report=run_dual_model_benchmark(samples,root,fake,fake,model_names=("one","two"))
        return samples,report
    def test_strict_calibration_fails_before_audio_provider(self):
        from test_microgen_tts_release_audit import setup
        from microgen_tts_autonomous_campaign import (
            run_autonomous_campaign,AutonomousCampaignError,
        )
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"lecture";stage.mkdir();setup(stage)
            calls=[]
            def forbidden(_):calls.append(1);return "unapproved"
            from unittest.mock import patch
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                with self.assertRaisesRegex(AutonomousCampaignError,"calibration"):
                    run_autonomous_campaign(stage,root/"qa",forbidden,forbidden,
                                  models=("one","two"),require_calibration=True)
            self.assertEqual(calls,[])
            self.assertFalse((root/"qa").exists())

    def test_real_reference_calibration_allows_technical_stage_without_human(self):
        from unittest.mock import patch
        from test_microgen_tts_release_audit import setup
        from microgen_tts_autonomous_campaign import run_autonomous_campaign
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bench=root/"benchmark";bench.mkdir()
            samples,report=self.prepare(bench)
            stage=root/"lecture";stage.mkdir();setup(stage)
            with patch("microgen_tts_release_audit.check_video",
                       return_value={"seconds":1.5}):
                result=run_autonomous_campaign(
                    stage,root/"qa",lambda _:"The why value exists.",
                    lambda _:"The why value exists.",
                    models=("one","two"),
                    calibration_bundle=(samples,report,bench),
                    require_calibration=True)
            self.assertTrue(result["automated_technical_qa_passed"])
            self.assertEqual(result["model_calibration_status"],
                             "QUALIFIED_FOR_TESTED_Y_PRONUNCIATION_ONLY")
            self.assertFalse(result["human_approval_required"])
            self.assertFalse(result["published"])

    def test_good_pair_qualifies_only_for_narrow_family(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);samples,report=self.prepare(root)
            result=check_model_calibration(samples,report,root,expected_models=("one","two"))
            self.assertTrue(result["qualified_for_tested_risk_family"])
            self.assertEqual(result["case_count"],2)
            self.assertFalse(result["manual_gate"])
            self.assertIn("no general phonetic certification",result["scope"])
    def test_models_that_normalize_both_variants_fail_calibration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);samples,report=self.prepare(root,wrong=True)
            result=check_model_calibration(samples,report,root,expected_models=("one","two"))
            self.assertFalse(result["qualified_for_tested_risk_family"])
            self.assertEqual(result["coverage"],0)
    def test_invalid_metrics_or_model_identity_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);samples,report=self.prepare(root)
            report["metrics"]["acceptance_pass"]=False
            with self.assertRaises(ModelCalibrationError):
                check_model_calibration(samples,report,root,expected_models=("one","two"))
            report["metrics"]["acceptance_pass"]=True
            with self.assertRaises(ModelCalibrationError):
                check_model_calibration(samples,report,root,expected_models=("A","B"))
    def test_changed_actual_wav_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);samples,report=self.prepare(root)
            (root/"before.wav").write_bytes(b"changed")
            with self.assertRaises(ModelCalibrationError):
                check_model_calibration(samples,report,root,expected_models=("one","two"))
    def test_incomplete_and_tampered_transcripts_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);samples,report=self.prepare(root)
            report["actual_audio_evidence"][0]["transcripts"][0]="why value why value"
            with self.assertRaises(ModelCalibrationError):
                check_model_calibration(samples,report,root,expected_models=("one","two"))
