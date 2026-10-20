import tempfile,unittest
from pathlib import Path
from test_microgen_tts_acoustic_benchmark import manifest
from microgen_tts_contrastive_calibration import calibrate,ContrastCalibrationError

class DirectPhonemeCalibrationTests(unittest.TestCase):
    def test_both_models_explicitly_catch_bad_and_clear_good(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=manifest(p)
            def judgement(f,_):return "YAY" if f.name=="before.wav" else "WHY"
            verdict=calibrate(data,p,judgement,judgement,models=("A","B"))
            self.assertTrue(verdict["calibrated_for_tested_y_value_family"])
            self.assertFalse(verdict["general_phonetic_validity"])
            self.assertFalse(verdict["human_approval"])
    def test_conventional_spelling_or_wrong_audio_not_certified(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=manifest(p)
            verdict=calibrate(data,p,lambda *_:"y-value",lambda *_:"WHY",models=("A","B"))
            self.assertFalse(verdict["calibrated_for_tested_y_value_family"])
            self.assertEqual(verdict["observed_coverage"],0)
    def test_ambiguous_or_outage_rejected_without_human_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=manifest(p)
            def error(*_):raise RuntimeError("provider down")
            result=calibrate(data,p,error,lambda *_:"YAY",models=("A","B"))
            self.assertFalse(result["calibrated_for_tested_y_value_family"])
    def test_source_hash_change_refused_before_judgement(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=manifest(p)
            (p/"before.wav").write_bytes(b"damaged")
            called=[]
            with self.assertRaises(Exception):
                calibrate(data,p,lambda *_:called.append(True),lambda *_:called.append(True),models=("A","B"))
            self.assertEqual(called,[])
    def test_same_model_and_too_many_calls_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=manifest(p)
            for names in (("A","A"),("","B")):
                with self.assertRaises(ContrastCalibrationError):
                    calibrate(data,p,lambda *_:"WHY",lambda *_:"WHY",models=names)
            with self.assertRaises(ContrastCalibrationError):
                calibrate(data,p,lambda *_:"WHY",lambda *_:"WHY",models=("A","B"),max_requests=3)
