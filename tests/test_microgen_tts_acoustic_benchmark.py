import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from microgen_tts_acoustic_benchmark import (
    detect_yay_case,run_dual_model_benchmark,
)
from microgen_tts_benchmark import BenchmarkError

def manifest(root):
    samples=[]
    for ident,label in [("before","defect"),("after","correct")]:
        filename=ident+".wav"
        (root/filename).write_bytes(ident.encode())
        samples.append({"id":ident,"label":label,"filename":filename,
                        "sha256":hashlib.sha256(ident.encode()).hexdigest(),
                        "expected_occurrences":2,
                        "cue_family":"math_y_value"})
    return {"schema_version":1,"samples":samples}

class IndependentAudioBenchmarkTests(unittest.TestCase):
    def test_yay_both_occurrences_is_flag(self):
        self.assertEqual(detect_yay_case("one yay value, another yay value."),"flag")
    def test_clear_requires_explicit_why_at_both_occurrences(self):
        self.assertEqual(detect_yay_case("one why value, another why value."),"clear")
        self.assertEqual(detect_yay_case("one y-value, another y-value."),"unknown")
        self.assertEqual(detect_yay_case("one why value."),"unknown")
        self.assertEqual(detect_yay_case("[unclear] why value why value"),"unknown")
    def test_one_error_even_with_other_correct_flags(self):
        self.assertEqual(detect_yay_case("why value and yay value"),"flag")
    def test_real_failures_count_as_false_negative_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            out=run_dual_model_benchmark(
                cases,p,lambda f:"why value and why value",
                lambda f:"why value and why value",
                model_names=("one","two"))
            self.assertEqual(out["metrics"]["confusion"]["FN"],1)
            self.assertFalse(out["metrics"]["acceptance_pass"])
            self.assertEqual(out["metrics"]["coverage"],1)
    def test_real_correct_classification_scores_both(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            def recognize(f):
                return ("yay value and yay value" if f.name=="before.wav"
                        else "why value and why value")
            r=run_dual_model_benchmark(cases,p,recognize,recognize,
                model_names=("one","two"))
            self.assertEqual(r["metrics"]["confusion"]["TP"],1)
            self.assertEqual(r["metrics"]["confusion"]["TN"],1)
            self.assertTrue(r["metrics"]["acceptance_pass"])
            self.assertFalse(r["population_error_rate_established"])
    def test_disagreement_is_unknown_not_clear(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            r=run_dual_model_benchmark(cases,p,
                lambda f:"yay value yay value",
                lambda f:"why value why value",
                model_names=("one","two"))
            self.assertEqual(r["metrics"]["confusion"]["UNKNOWN"],2)
            self.assertEqual(r["metrics"]["coverage"],0)
    def test_outage_bounded_across_cases(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            invoked=[]
            def fail(f):invoked.append(f);raise RuntimeError("quota")
            r=run_dual_model_benchmark(cases,p,fail,
                lambda f:"why value why value",model_names=("one","two"))
            self.assertEqual(len(invoked),1)
            self.assertEqual(r["metrics"]["confusion"]["UNKNOWN"],2)
            self.assertEqual(r["unavailable_models"],["one"])
    def test_sha_drift_checked_before_provider(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            (p/"before.wav").write_bytes(b"tampered")
            called=[]
            with self.assertRaises(BenchmarkError):
                run_dual_model_benchmark(cases,p,
                    lambda f:called.append(f),lambda f:called.append(f),
                    model_names=("one","two"))
            self.assertEqual(called,[])
    def test_same_model_id_not_independent(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cases=manifest(p)
            with self.assertRaises(BenchmarkError):
                run_dual_model_benchmark(cases,p,lambda f:"",lambda f:"",
                    model_names=("same","same"))
