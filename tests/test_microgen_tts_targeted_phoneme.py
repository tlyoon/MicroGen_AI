import json,tempfile,unittest
from pathlib import Path
from test_microgen_tts_acoustic_benchmark import manifest
from microgen_tts_targeted_phoneme import scan_stage,eligible_y_risks,TargetedProbeError

class ScopedPhonemeTests(unittest.TestCase):
    def fixture(self,root):
        bench=root/"reference";bench.mkdir();ref=manifest(bench)
        stage=root/"lesson";stage.mkdir()
        (stage/"script_tts.json").write_text(json.dumps({"slides":[{"slide":1,"tts_text":"The y-value is positive."},{"slide":2,"tts_text":"Another sentence without variables."}]}))
        (stage/"slide1.wav").write_bytes(b"lesson")
        (stage/"slide2.wav").write_bytes(b"another")
        def judge(p,_):return "YAY" if p.name=="before.wav" else "WHY"
        return stage,bench,ref,judge
    def test_detects_only_reviewed_y_value_compound(self):
        self.assertEqual(len(eligible_y_risks("The y-value of x-axis.")),1)
        self.assertEqual(eligible_y_risks("Yale is popular, x-axis."),[])
    def test_known_good_calibration_allows_targeted_slide(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage,bench,ref,judge=self.fixture(p)
            result=scan_stage(stage,ref,bench,judge,judge,models=("A","B"))
            self.assertFalse(result["blocked"])
            self.assertEqual(result["risk_slide_count"],1)
            self.assertFalse(result["verified_error_free"])
            self.assertFalse(result["published"])
    def test_bad_calibration_prevents_all_target_slide_calls(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage,bench,ref,_=self.fixture(p)
            calls=[]
            def uncalibrated(path,_):
                calls.append(path.name);return "WHY"
            r=scan_stage(stage,ref,bench,uncalibrated,uncalibrated,models=("A","B"))
            self.assertTrue(r["blocked"])
            self.assertEqual(r["probe_rows"],[])
            self.assertNotIn("slide1.wav",calls)
    def test_detected_yay_remains_technical_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage,bench,ref,_=self.fixture(p)
            def first(path,_):
                return "YAY" if path.name in ("before.wav","slide1.wav") else "WHY"
            r=scan_stage(stage,ref,bench,first,first,models=("A","B"))
            self.assertTrue(r["blocked"])
            self.assertEqual(r["probe_rows"][0]["status"],"DETECTED_YAY_RISK")
    def test_scope_limit_refuses_before_any_calls(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage,bench,ref,judge=self.fixture(p)
            with self.assertRaises(TargetedProbeError):
                scan_stage(stage,ref,bench,judge,judge,models=("A","B"),max_probe_slides=0)
