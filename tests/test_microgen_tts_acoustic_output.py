import tempfile
import unittest
from pathlib import Path
import microgen_tts_acoustic_qa as a

class AcousticReceiptIsolationTests(unittest.TestCase):
    def test_source_descendants_and_ancestors_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"lesson";source.mkdir()
            for proposed in (source/"new.json",source/"scratch"/"new.json",root):
                with self.subTest(path=str(proposed)):
                    with self.assertRaises(a.AcousticQAError):
                        a.require_external_new_receipt(source,proposed)
    def test_external_report_is_available_and_collision_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);source=p/"lecture";source.mkdir()
            target=p/"candidate-evidence.json"
            self.assertEqual(a.require_external_new_receipt(source,target),target.resolve(strict=False))
            target.write_text("do not alter")
            with self.assertRaises(a.AcousticQAError):
                a.require_external_new_receipt(source,target)
            self.assertEqual(target.read_text(),"do not alter")
    def test_existing_symlink_alias_never_bypasses_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);source=p/"lecture";source.mkdir();alias=p/"alias"
            try:alias.symlink_to(source,target_is_directory=True)
            except (OSError,NotImplementedError) as e:self.skipTest(str(e))
            with self.assertRaises(a.AcousticQAError):
                a.require_external_new_receipt(source,alias/"evidence.json")
    def test_cli_preflight_fails_before_credentials_and_model_calls(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);source=p/"lecture";source.mkdir()
            with self.assertRaises(a.AcousticQAError):
                a.main([str(source),"--new-report",str(source/"new.json")])
            self.assertFalse((source/"new.json").exists())
