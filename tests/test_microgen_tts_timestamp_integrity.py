import json,tempfile,unittest
from pathlib import Path
from test_microgen_tts_snippet_integrity import SnippetIntegrityTests
from microgen_tts_snippet_integrity import verify_snippets,SnippetIntegrityError

class TimestampIntegrityTests(unittest.TestCase):
    def test_valid_sample_derived_timestamps(self):
        with tempfile.TemporaryDirectory() as td:
            source,folder=SnippetIntegrityTests().setup(Path(td))
            self.assertTrue(verify_snippets(source,folder)["structural_integrity_passed"])
    def test_forged_seconds_fail_even_if_pcm_identical(self):
        with tempfile.TemporaryDirectory() as td:
            source,folder=SnippetIntegrityTests().setup(Path(td))
            receipt=folder/"snippet_manifest.json"
            data=json.loads(receipt.read_text())
            data["snippets"][0]["start_seconds"]=.5
            receipt.write_text(json.dumps(data))
            with self.assertRaisesRegex(SnippetIntegrityError,"Timestamp/sample"):
                verify_snippets(source,folder)
    def test_missing_and_nonfinite_timestamps_fail(self):
        for bad in (None,float("nan"),"0.1",True):
            with self.subTest(bad=str(bad)),tempfile.TemporaryDirectory() as td:
                source,folder=SnippetIntegrityTests().setup(Path(td))
                receipt=folder/"snippet_manifest.json"
                data=json.loads(receipt.read_text())
                data["snippets"][0]["end_seconds"]=bad
                receipt.write_text(json.dumps(data))
                with self.assertRaises(SnippetIntegrityError):
                    verify_snippets(source,folder)
