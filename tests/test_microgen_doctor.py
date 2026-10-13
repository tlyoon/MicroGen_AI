import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from microgen_doctor import audit_tree,inspect_environment

class DoctorTests(unittest.TestCase):
    def test_bounded_audit_counts_only_source_backed_subchapters(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            (p/"1"/"1.1").mkdir(parents=True)
            (p/"1"/"1.2").mkdir(parents=True)
            (p/"archive"/"99.1").mkdir(parents=True)
            (p/"1"/"1.1"/"source.pdf").write_bytes(b"source")
            (p/"1"/"1.1"/"slides.pdf").write_bytes(b"slide")
            (p/"1"/"1.1"/"script.txt").write_bytes(b"script")
            (p/"1"/"1.1"/"slides.mp4").write_bytes(b"MP4")
            (p/"1"/"1.2"/"source.pdf").write_bytes(b"source")
            v=audit_tree(p)
            self.assertEqual(v["source_count"],2)
            self.assertEqual(v["video_file_count"],1)
            self.assertEqual(v["verified_receipt_count"],0)
            self.assertEqual([x["subchapter"] for x in v["incomplete"]],["1.2"])
    def test_environment_does_not_expose_secret_values(self):
        with tempfile.TemporaryDirectory() as root:
            v="AIzaTEST-PRIVATE-DO-NOT-LEAK"
            with mock.patch.dict("os.environ",{"GEMINI_API_KEY_1":v,"MICROVID_CONFIG_DIR":root}):
                state=inspect_environment(Path(root))
            self.assertTrue(state["checks"]["gemini_key_configured"])
            self.assertNotIn(v,json.dumps(state))
    def test_missing_root_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                audit_tree(Path(root)/"not-present")

if __name__=="__main__":unittest.main()
