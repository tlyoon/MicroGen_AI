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


    def test_detects_installed_but_unimportable_sdk(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch("microgen_doctor.subprocess.run") as run:
                run.return_value=mock.Mock(returncode=1)
                result=inspect_environment(Path(root))
            self.assertFalse(result["checks"]["gemini_tts_sdks_importable"])
            self.assertFalse(result["ok"])


    def test_doctor_reports_unsuitable_scratch_disk(self):
        with tempfile.TemporaryDirectory() as root:
            fake={"work_root":root,"volume_checked":root,"free_gb":0.9,
                  "required_gb":8.0,"enough_space":False}
            with mock.patch("microgen_doctor.subprocess.run",
                            return_value=mock.Mock(returncode=0)), \
                 mock.patch("microgen_quality.scratch_disk_status",return_value=fake):
                info=inspect_environment(Path(root),work_root=Path(root))
            self.assertFalse(info["checks"]["scratch_disk_capacity"])
            self.assertFalse(info["ok"])
            self.assertEqual(info["scratch_disk"]["free_gb"],0.9)


    def test_separate_docling_interpreter_is_checked_before_generation(self):
        with tempfile.TemporaryDirectory() as root:
            from unittest.mock import Mock
            with mock.patch("microgen_doctor.subprocess.run",
                            side_effect=[Mock(returncode=0),Mock(returncode=1)]) as run:
                state=inspect_environment(Path(root),docling_py="D:/Docling/python.exe")
            self.assertEqual(run.call_count,2)
            self.assertFalse(state["checks"]["docling_extraction_importable"])
            self.assertFalse(state["ok"])

if __name__=="__main__":unittest.main()
