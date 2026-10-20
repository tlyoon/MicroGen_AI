import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_release_audit import setup
from test_microgen_tts_acoustic_benchmark import manifest
from microgen_tts_autonomous_campaign import run_autonomous_campaign,AutonomousCampaignError

class CampaignPhoneticTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/"stage";stage.mkdir();setup(stage)
        reference=root/"refs";reference.mkdir()
        samples=manifest(reference)
        def judge(path,prompt):
            return "YAY" if path.name=="before.wav" else "WHY"
        return stage,(samples,reference),judge
    def test_strict_correct_judgments_enable_normal_asr(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,ref,judge=self.fixture(root)
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                result=run_autonomous_campaign(stage,root/"packet",
                    lambda _:"The why value exists.",lambda _:"The why value exists.",
                    models=("one","two"),phonetic_reference=ref,
                    phonetic_judges=(judge,judge),require_calibrated_phoneme=True)
            self.assertTrue(result["strict_phonetic_probe_enabled"])
            self.assertTrue(result["narrow_phonetic_verification"]["technically_cleared"])
            self.assertFalse(result["published"])
            self.assertTrue((root/"packet"/"calibrated_phonetic_evidence.json").is_file())
    def test_failed_real_reference_calibration_blocks_before_asr(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,ref,_=self.fixture(root);calls=[]
            def asr(_):calls.append(1);return "The why value exists."
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                with self.assertRaisesRegex(AutonomousCampaignError,"Phonetic calibration"):
                    run_autonomous_campaign(stage,root/"packet",asr,asr,models=("one","two"),
                        phonetic_reference=ref,
                        phonetic_judges=(lambda *_:"UNKNOWN",lambda *_:"UNKNOWN"),
                        require_calibrated_phoneme=True)
            self.assertEqual(calls,[])
            self.assertFalse((root/"packet").exists())
    def test_no_manual_reference_is_not_silent_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,_,_=self.fixture(root)
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                with self.assertRaisesRegex(AutonomousCampaignError,"reference WAVs"):
                    run_autonomous_campaign(stage,root/"packet",lambda _:"okay",
                        lambda _:"okay",models=("one","two"),
                        require_calibrated_phoneme=True)
