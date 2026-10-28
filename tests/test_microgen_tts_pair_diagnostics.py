import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pair_diagnostics import analyze_pair,validate_output,main,PairDiagnosticError
from microgen_tts_pcm_features import file_sha256

class RealPairReportTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/"source";stage.mkdir()
        a=stage/"before.wav";b=stage/"after.wav"
        make(a,1000);make(b,1500)
        return a,b,file_sha256(a),file_sha256(b)
    def test_unclassified_audio_report_does_not_publish(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,b,ha,hb=self.fixture(root)
            result=analyze_pair(a,b,ha,hb)
            self.assertTrue(result["diagnostic_only"])
            self.assertIsNone(result["phonetic_error_detected"])
            self.assertFalse(result["machine_release_approved"])
            self.assertFalse(result["phonetic_accuracy_certified"])
    def test_mismatched_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,b,ha,hb=self.fixture(root)
            with self.assertRaises(PairDiagnosticError):
                analyze_pair(a,b,"0"*64,hb)
            b.write_bytes(b"corrupted")
            with self.assertRaises(PairDiagnosticError):
                analyze_pair(a,b,ha,hb)
    def test_never_create_report_in_source_tree_or_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,b,ha,hb=self.fixture(root)
            with self.assertRaises(PairDiagnosticError):
                validate_output(a,b,a.parent/"new.json")
            report=root/"qa.json"
            self.assertEqual(main([str(a),str(b),str(report),
                    "--before-sha256",ha,"--after-sha256",hb]),0)
            old=report.read_bytes()
            with self.assertRaises(PairDiagnosticError):
                validate_output(a,b,report)
            self.assertEqual(old,report.read_bytes())
            self.assertEqual(file_sha256(a),ha)
    def test_invalid_hash_format_and_same_source_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,b,ha,hb=self.fixture(root)
            with self.assertRaises(PairDiagnosticError):
                analyze_pair(a,b,"invalid",hb)
            with self.assertRaises(PairDiagnosticError):
                analyze_pair(a,a,ha,ha)
