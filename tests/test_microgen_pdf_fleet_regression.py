"""Fleet-level PDF intake regressions: never repair each source manually.

Synthetic PDFs only. No textbook bytes, provider requests, TTS, or media rendering.
"""
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz

from microgen_source_pdf_intake import (
    SourcePDFIntakeError, inspect_source_pdf, create_intake_receipt,
)
from microgen_source_safe_orchestrator import digest


def source_pdf(directory, searchable_pages):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "source.pdf"
    with fitz.open() as doc:
        for searchable in searchable_pages:
            page = doc.new_page(width=612, height=792)
            if searchable:
                page.insert_text(
                    (50, 80),
                    "Figure 2.3 This physical system has velocity and "
                    "acceleration measurements for the original source.",
                )
            page.draw_rect(fitz.Rect(50, 110, 200, 230))
        doc.save(path)
    return path


class FleetPDFRegressionTests(unittest.TestCase):
    def test_readiness_is_consistent_across_different_source_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cases = [
                ("all_text", [True] * 10, "SOURCE_TEXT_READY"),
                ("threshold", [True] * 7 + [False] * 3, "SOURCE_TEXT_READY"),
                ("below_threshold", [True] * 6 + [False] * 4,
                 "SOURCE_TEXT_EXTRACTION_REQUIRED"),
                ("scanned", [False] * 10, "SOURCE_TEXT_EXTRACTION_REQUIRED"),
            ]
            for name, pages, expected in cases:
                with self.subTest(name=name):
                    pdf = source_pdf(base / name, pages)
                    before = digest(pdf)
                    data = inspect_source_pdf(pdf.parent)
                    self.assertEqual(data["source_text_readiness"], expected)
                    self.assertEqual(data["page_count"], len(pages))
                    self.assertEqual(data["source_pdf_sha256"], before)
                    self.assertEqual(digest(pdf), before)
                    self.assertFalse(data["publication_allowed"])

    def test_cross_section_runs_preserve_every_original_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = [source_pdf(root / f"section_{i}", [True, True])
                       for i in range(3)]
            hashes = [digest(s) for s in sources]
            for index, pdf in enumerate(sources):
                receipt = create_intake_receipt(pdf.parent, root / f"receipt_{index}")
                self.assertEqual(receipt["source_pdf_sha256"], hashes[index])
                self.assertFalse(receipt["publication_allowed"])
            self.assertEqual([digest(s) for s in sources], hashes)

    def test_corrupt_one_source_does_not_require_repairing_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = source_pdf(root / "valid", [True, True])
            damaged = root / "damaged"
            damaged.mkdir()
            (damaged / "source.pdf").write_bytes(b"broken pdf" * 100)
            original_hash = digest(valid)
            with self.assertRaises(SourcePDFIntakeError):
                inspect_source_pdf(damaged)
            self.assertEqual(inspect_source_pdf(valid.parent)["source_pdf_sha256"],
                             original_hash)
            self.assertEqual(digest(valid), original_hash)


if __name__ == "__main__":
    unittest.main()
