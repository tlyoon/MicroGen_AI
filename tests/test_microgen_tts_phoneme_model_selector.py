import tempfile,unittest
from pathlib import Path
from test_microgen_tts_acoustic_benchmark import manifest
from microgen_tts_contrastive_calibration import calibrate
from microgen_tts_phoneme_model_selector import select_pair,SelectionError

class ModelSelectorTests(unittest.TestCase):
    def sample(self,p,good=True):
        reference=manifest(p)
        def judge(w,_):
            return ("YAY" if w.name=="before.wav" else "WHY") if good else "UNKNOWN"
        report=calibrate(reference,p,judge,judge,models=("judge-A","judge-B"))
        report["live_audio_requests_requested"]=True
        return reference,report
    def test_picks_only_verified_real_reference_success(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ref,good=self.sample(p)
            bad=dict(good);bad["calibrated_for_tested_y_value_family"]=False
            result=select_pair(ref,p,[bad,good])
            self.assertEqual(result["selected_models"],["judge-A","judge-B"])
            self.assertFalse(result["populational_phonetic_accuracy_proven"])
            self.assertFalse(result["published"])
    def test_no_pair_when_both_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ref,bad=self.sample(p,good=False)
            result=select_pair(ref,p,[bad])
            self.assertIsNone(result["selected_models"])
            self.assertEqual(result["selection_status"],"NO_QUALIFIED_AUDIO_PAIR")
    def test_offline_not_real_is_unqualified_even_if_labels_right(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ref,good=self.sample(p)
            good["live_audio_requests_requested"]=False
            result=select_pair(ref,p,[good])
            self.assertIsNone(result["selected_models"])
            self.assertEqual(result["candidate_results"][0]["reason"],"NOT_OBSERVED_LIVE_CALLS")
    def test_tampered_hash_or_model_label_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ref,good=self.sample(p)
            good["cases"][0]["model_answers"][0]["wav_sha256"]="0"*64
            result=select_pair(ref,p,[good])
            self.assertIsNone(result["selected_models"])
    def test_attempt_limit_and_duplicate_report_limit(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ref,good=self.sample(p)
            with self.assertRaises(SelectionError):
                select_pair(ref,p,[good]*13)
            with self.assertRaises(SelectionError):
                select_pair(ref,p,[good],max_reports=0)
