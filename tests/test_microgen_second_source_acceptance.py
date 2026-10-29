"""Offline source-stage evidence regression. No Gemini/TTS/API calls."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_second_source_acceptance import (
    SourceCampaignAcceptanceError, verify_source_campaign,
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup_stage(root: Path):
    original = root / "original" / "source.pdf"
    original.parent.mkdir()
    with fitz.open() as pdf:
        for n in range(2):
            page = pdf.new_page(width=610, height=410)
            page.insert_text((30, 60),
                "Figure 1.1 Source-grounded physical model of the position "
                "versus time for a moving object with measured uncertainty.")
            page.insert_text((30, 95),
                "For the original mechanical system, the position x varies "
                "continuously with time t and this diagram introduces axes.")
        pdf.save(original)
    stage = root / "scratch" / "1.1"
    stage.mkdir(parents=True)
    (stage / "source.pdf").write_bytes(original.read_bytes())
    pages = []
    with fitz.open(original) as pdf:
        for i, pg in enumerate(pdf, 1):
            folder = stage / "pages" / f"page_{i}"
            folder.mkdir(parents=True)
            single = folder / f"page_{i}.pdf"
            with fitz.open() as piece:
                piece.insert_pdf(pdf, from_page=i - 1, to_page=i - 1)
                piece.save(single)
            png = folder / f"page_{i}.png"
            Image.new("RGB", (300, 250), "white").save(png)
            pages.append({
                "page": i, "pdf_sha256": digest(single),
                "png_sha256": digest(png), "figures": []
            })
    (stage / "figure_extraction_receipt.json").write_text(
        json.dumps({
            "status": "OFFLINE_SOURCE_FIGURE_EXTRACTION_COMPLETE",
            "source_sha256": digest(original), "page_count": 2,
            "pages": pages, "gemini_invoked": False,
            "tts_invoked": False, "publication_allowed": False,
        }), encoding="utf-8"
    )
    (stage / ".microgen_checkpoint.json").write_text(
        json.dumps({
            "completed": {"figure_extraction": "2026-10-29T01:00:00Z"},
            "source_signature": {"size": original.stat().st_size},
            "package_commit": "abcdef" * 6 + "abcd",
        }), encoding="utf-8"
    )
    return original, stage


class SourceCampaignTests(unittest.TestCase):
    def test_new_source_and_repeat_are_readonly_and_not_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            old = digest(original)
            destination = root / "verified"
            receipt = verify_source_campaign(original, stage, destination)
            self.assertEqual(receipt["status"],
                "SOURCE_ONLY_STAGE_COMPLETE_PROVIDER_DEPENDENT_STAGES_PENDING")
            self.assertEqual(receipt["source_pages"], 2)
            self.assertEqual(receipt["docling_extracted_figures"], 0)
            self.assertFalse(receipt["second_end_to_end_generation_passed"])
            self.assertFalse(receipt["publication_allowed"])
            self.assertFalse(receipt["provider_authorized_by_this_report"])
            self.assertFalse(receipt["generated_wavs"])
            self.assertEqual(old, digest(original))
            report_file = destination / "source_campaign_readiness.json"
            prior = digest(report_file)
            again = verify_source_campaign(original, stage, destination)
            self.assertEqual(again, receipt)
            self.assertEqual(prior, digest(report_file))

    def test_original_source_hash_mismatch_blocks_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            original.write_bytes(original.read_bytes() + b"\nchanged")
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, root / "verified")
            self.assertFalse((root / "verified").exists())

    def test_partial_source_page_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            (stage / "pages" / "page_2" / "page_2.png").unlink()
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, root / "verified")
            self.assertFalse((root / "verified").exists())

    def test_missing_completed_checkpoint_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            cp = stage / ".microgen_checkpoint.json"
            state = json.loads(cp.read_text())
            state["completed"].clear()
            cp.write_text(json.dumps(state))
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, root / "verified")

    def test_code_commit_pin_requires_exact_unchanged_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, root / "verified",
                                       expected_commit="0" * 40)
            self.assertFalse((root / "verified").exists())

    def test_existing_report_fails_on_checkpoint_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            report = root / "verified"
            verify_source_campaign(original, stage, report)
            cp = stage / ".microgen_checkpoint.json"
            cp.write_text(cp.read_text() + " ")
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, report)

    def test_output_under_original_source_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, stage = setup_stage(root)
            with self.assertRaises(SourceCampaignAcceptanceError):
                verify_source_campaign(original, stage, original.parent / "report")
            self.assertFalse((original.parent / "report").exists())


if __name__ == "__main__":
    unittest.main()
