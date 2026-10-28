"""No-network, no-TTS source-only intake regression."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

from microgen_source_pdf_intake import (
    SourcePDFIntakeError, create_intake_receipt, inspect_source_pdf,
)
from microgen_source_safe_orchestrator import digest


def make_pdf(where, *, text=True, pages=2):
    folder = Path(where)
    folder.mkdir(exist_ok=True)
    source = folder / "source.pdf"
    with fitz.open() as doc:
        for _ in range(pages):
            page = doc.new_page(width=780, height=320)
            if text:
                page.insert_text(
                    (30, 42),
                    "Figure 1.2 The measured position and velocity are "
                    "related by the equation y = 3x + 2.",
                )
                page.insert_text((30, 80), "tan theta = 2.5")
            page.draw_rect(fitz.Rect(80, 110, 320, 275), width=1.6)
        doc.save(source)
    return source


class SourceOnlyIntakeTests(unittest.TestCase):
    def test_real_readable_source_intake_does_not_change_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_pdf(root / "protected")
            before = digest(source)
            result = create_intake_receipt(source.parent, root / "reports")
            self.assertEqual(result["source_text_readiness"], "SOURCE_TEXT_READY")
            self.assertEqual(result["page_count"], 2)
            self.assertGreaterEqual(result["source_figure_candidates"], 1)
            self.assertGreaterEqual(result["source_math_line_candidates"], 1)
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["generated_audio"])
            self.assertFalse(result["generated_slides"])
            self.assertFalse(result["narrated_element_sync_verified"])
            self.assertEqual(digest(source), before)
            self.assertTrue((root/"reports"/"source_intake_receipt.json").is_file())
            self.assertTrue((root/"reports"/"figure_geometry.json").is_file())
            self.assertTrue((root/"reports"/"equation_geometry.json").is_file())

    def test_scanned_source_is_not_silently_text_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_pdf(root / "protected", text=False)
            result = create_intake_receipt(source.parent, root / "reports")
            self.assertEqual(
                result["source_text_readiness"], "SOURCE_TEXT_EXTRACTION_REQUIRED")
            self.assertEqual(result["next_action"], "RESTORE_SEARCHABLE_PDF_TEXT")
            self.assertFalse(result["publication_allowed"])

    def test_source_location_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=make_pdf(root/"protected")
            for invalid in (source.parent/"internal", source.parent):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(SourcePDFIntakeError):
                        create_intake_receipt(source.parent, invalid)
            existing=root/"existing"
            existing.mkdir()
            with self.assertRaises(SourcePDFIntakeError):
                create_intake_receipt(source.parent, existing)

    def test_missing_source_file_rejected_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"protected"
            src.mkdir()
            with self.assertRaises(SourcePDFIntakeError):
                create_intake_receipt(src,root/"out")
            self.assertFalse((root/"out").exists())

    def test_corrupt_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"protected";src.mkdir()
            (src/"source.pdf").write_bytes(b"Not a PDF file" * 100)
            with self.assertRaises(SourcePDFIntakeError):
                inspect_source_pdf(src)

    def test_source_changed_during_geometry_stops_and_cleans_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=make_pdf(root/"protected")
            from microgen_source_pdf_intake import digest as real_digest
            calls=[0]
            def different_on_third_call(path):
                calls[0]+=1
                return "0"*64 if calls[0]>=3 else real_digest(path)
            with patch("microgen_source_pdf_intake.digest",
                       side_effect=different_on_third_call):
                with self.assertRaises(SourcePDFIntakeError):
                    create_intake_receipt(source.parent,root/"out")
            self.assertFalse((root/"out").exists())

    def test_source_directory_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=make_pdf(root/"protected")
            alias=root/"linked_original"
            try:
                alias.symlink_to(source.parent, target_is_directory=True)
            except OSError:
                self.skipTest("Windows symlink privilege not available")
            with self.assertRaises(SourcePDFIntakeError):
                create_intake_receipt(alias,root/"out")
            self.assertFalse((root/"out").exists())

    def test_unrelated_directory_file_not_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=make_pdf(root/"protected")
            extra=source.parent/"keep.txt"
            extra.write_text("preserved",encoding="utf8")
            create_intake_receipt(source.parent,root/"out")
            self.assertEqual(extra.read_text(encoding="utf8"),"preserved")


if __name__=="__main__":
    unittest.main()
