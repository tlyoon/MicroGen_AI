import json
import tempfile
import unittest
from pathlib import Path

import microgen_tts_benchmark as b

BASE={"schema_version":1,"samples":[
 {"id":"known-bad","filename":"before.wav","sha256":"a"*64,"label":"defect"},
 {"id":"known-good","filename":"after.wav","sha256":"b"*64,"label":"correct"}]}

class RealWavBenchmarkTests(unittest.TestCase):
    def test_unknown_is_not_zero_errors(self):
        r=b.score_recognition(BASE,{})
        self.assertEqual(r["coverage"],0)
        self.assertIsNone(r["recall"])
        self.assertFalse(r["acceptance_pass"])
        self.assertEqual(r["confusion"]["UNKNOWN"],2)
    def test_false_negative_false_positive(self):
        r=b.score_recognition(BASE,{"known-bad":"clear","known-good":"flag"})
        self.assertEqual(r["confusion"]["FN"],1)
        self.assertEqual(r["confusion"]["FP"],1)
        self.assertFalse(r["acceptance_pass"])
    def test_full_coverage_not_population_claim(self):
        r=b.score_recognition(BASE,{"known-bad":"flag","known-good":"clear"})
        self.assertTrue(r["acceptance_pass"])
        self.assertEqual(r["recall"],1)
        self.assertIn("labeled samples",r["notice"])
    def test_unknown_key_and_unreviewed_label_rejected(self):
        with self.assertRaises(b.BenchmarkError):
            b.score_recognition(BASE,{"other":"flag"})
        broken=json.loads(json.dumps(BASE))
        broken["samples"][0]["label"]="suspected"
        with self.assertRaises(b.BenchmarkError):
            b.validate_reference(broken)
    def test_real_bytes_hash_checked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            broken=json.loads(json.dumps(BASE))
            (root/"before.wav").write_bytes(b"bad")
            (root/"after.wav").write_bytes(b"good")
            import hashlib
            broken["samples"][0]["sha256"]=hashlib.sha256(b"bad").hexdigest()
            broken["samples"][1]["sha256"]=hashlib.sha256(b"good").hexdigest()
            self.assertTrue(b.validate_reference(broken,root)["reference_audio_verified"])
            (root/"before.wav").write_bytes(b"tampered")
            with self.assertRaisesRegex(b.BenchmarkError,"checksum mismatch"):
                b.validate_reference(broken,root)
    def test_path_traversal_rejected(self):
        broken=json.loads(json.dumps(BASE))
        broken["samples"][0]["filename"]="../before.wav"
        with self.assertRaisesRegex(b.BenchmarkError,"Unsafe"):
            b.validate_reference(broken)
