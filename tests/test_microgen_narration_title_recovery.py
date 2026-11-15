"""Source-free title-wrap recovery regression; never invokes model services."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microgen_narration_title_recovery import recover_title_card
from microgen_quality import check_narration, QualityError


class _Slide:
    def __init__(self, text):
        self.text = text
    def get_text(self, how):
        assert how == "text"
        return self.text


class _Document:
    def __init__(self, text):
        self.text = text
    def __len__(self):
        return 1
    def __getitem__(self, pos):
        assert pos == 0
        return _Slide(self.text)
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class NarrationTitleRecoveryTests(unittest.TestCase):
    expected = "Unit 8: Numerical Integration by Parts"
    abbreviated = "Unit 8: Numerical Integration"

    def make_stage(self, root):
        folder = Path(root)
        (folder / "slides.pdf").write_bytes(b"Fake PDF: tested through page-text stub")
        (folder / "slides.tex").write_text(
            r"\title{" + self.expected + "}", encoding="utf8")
        (folder / "script.txt").write_text(
            f"**Slide 1 [1 sec]: \n{self.abbreviated}**\n\n",
            encoding="utf8")
        sidecar = {"slides": [{"slide": 1, "slide_id": "slide_01",
                               "title": self.abbreviated,
                               "narration": self.abbreviated,
                               "tts_text": self.abbreviated}]}
        (folder / "script_tts.json").write_text(
            json.dumps(sidecar), encoding="utf8")
        return folder

    def test_actual_quality_gate_rejects_then_source_recovery_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = self.make_stage(temp)
            with self.assertRaisesRegex(QualityError, "truncates the title"):
                check_narration(stage / "script.txt", stage / "script_tts.json", 1)
            with patch("pymupdf.open", return_value=_Document(
                    "Unit 8: Numerical Integration\nby Parts")):
                result = recover_title_card(stage)
                self.assertEqual(result["status"], "SOURCE_PDF_TITLE_WRAP_CORRECTED")
                self.assertTrue(result["changed"])
                check_narration(stage / "script.txt", stage / "script_tts.json", 1)
                second = recover_title_card(stage)
                self.assertEqual(second["status"], "ALREADY_FULL_SOURCE_TITLE")
            self.assertEqual(json.loads((stage / "script_tts.json").read_text(
                encoding="utf8"))["slides"][0]["narration"], self.expected)
            self.assertTrue((stage / ".microgen_source_title_recovery.json").is_file())

    def test_missing_pdf_title_does_not_silently_author_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = self.make_stage(temp)
            old = (stage / "script_tts.json").read_bytes()
            with patch("pymupdf.open", return_value=_Document(
                    "Unrelated source slide with a different heading")):
                result = recover_title_card(stage)
            self.assertEqual(result["status"], "TITLE_NOT_TEXT_ATTESTED_ABSTAINED")
            self.assertEqual(old, (stage / "script_tts.json").read_bytes())

    def test_unrelated_narrator_text_fails_closed_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = self.make_stage(temp)
            path = stage / "script_tts.json"
            data = json.loads(path.read_text(encoding="utf8"))
            data["slides"][0]["narration"] = "Not an original title prefix"
            path.write_text(json.dumps(data), encoding="utf8")
            with patch("pymupdf.open", return_value=_Document(self.expected)):
                result = recover_title_card(stage)
            self.assertEqual(result["status"], "UNRELATED_TITLE_ABSTAINED")
            self.assertFalse(result["changed"])

    def test_partial_two_file_repair_is_restart_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = self.make_stage(temp)
            data = json.loads((stage / "script_tts.json").read_text(encoding="utf8"))
            data["slides"][0].update(
                {"narration": self.expected, "tts_text": self.expected,
                 "title": self.expected})
            (stage / "script_tts.json").write_text(json.dumps(data), encoding="utf8")
            with patch("pymupdf.open", return_value=_Document(self.expected)):
                result = recover_title_card(stage)
            self.assertTrue(result["changed"])
            self.assertEqual(result["status"], "SOURCE_PDF_TITLE_WRAP_CORRECTED")
            check_narration(stage / "script.txt", stage / "script_tts.json", 1)


if __name__ == "__main__":
    unittest.main()
