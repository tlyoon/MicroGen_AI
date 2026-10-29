"""Real PDF draft authoring tests with synthetic source, no paid calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image

from microgen_offline_source_slide_draft import (
    SLIDES, OFFICIAL_SI_URL, OfflineSlideDraftError,
    create_draft, sha, verify_excerpt, normal,
)


def fixture(root):
    stage=root/"scratch"
    stage.mkdir()
    with fitz.open() as source:
        for n in range(1,5):
            page=source.new_page(width=2300,height=800)
            anchors=[x[2] for x in SLIDES if x[0]==n]
            for i,txt in enumerate(anchors):
                page.insert_text((40,80+i*50),txt,fontsize=11)
        source.save(stage/"source.pdf")
    Image.new("RGB",(400,300),"white").save(stage/"Figure 1.1.png")
    (stage/"offline_figure_mapping_receipt.json").write_text(
        json.dumps({"publication_allowed":False}),encoding="utf8")
    return stage


class OfflineSlideDraftContractTests(unittest.TestCase):
    def test_exact_source_match_is_required(self):
        self.assertTrue(verify_excerpt(
            "The length is a   12-meter reference.", "The length is a 12 meter reference"))
        self.assertFalse(verify_excerpt(
            "A different statement", "The source claim I expected"))

    def test_real_pdf_and_source_hash_manifest_and_bipm_external_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=fixture(root)
            src=sha(stage/"source.pdf")
            img=sha(stage/"Figure 1.1.png")
            with patch("microgen_offline_source_slide_draft._ensure_receipts"):
                record=create_draft(stage,root/"result")
            self.assertEqual(record["slide_count"],8)
            self.assertEqual(record["source_pdf_sha256"],src)
            self.assertEqual(record["source_figure_sha256"],img)
            self.assertEqual(sha(stage/"source.pdf"),src)
            self.assertFalse(record["publication_allowed"])
            self.assertFalse(record["gemini_or_tts_invoked"])
            self.assertFalse(record["narration_generated"])
            self.assertFalse(record["generated_wavs"])
            self.assertEqual(record["external_current_si_citation"],OFFICIAL_SI_URL)
            pdf=root/"result"/"slides_source_draft.pdf"
            self.assertEqual(sha(pdf),record["slideshow_sha256"])
            with fitz.open(pdf) as built:
                self.assertEqual(built.page_count,8)
                self.assertTrue(all(
                    abs(page.rect.width / page.rect.height - 16/9) < 0.01
                    for page in built))
                self.assertIn(normal("IMPORTANT SI UPDATE"),normal(built[3].get_text()))
                urls=[link.get("uri") for link in built[3].get_links()]
                self.assertIn(OFFICIAL_SI_URL,urls)
                self.assertTrue(all(
                    normal(SLIDES[i][1]) in normal(built[i].get_text())
                    for i in range(8)))
                self.assertGreaterEqual(len(built[4].get_images()),1)

    def test_tampered_or_missing_source_sentence_fails_without_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=fixture(root)
            with fitz.open() as src:
                for n in range(4):
                    pg=src.new_page(width=1000,height=500)
                    pg.insert_text((50,50),"Unrelated contents")
                src.save(stage/"source.pdf")
            with patch("microgen_offline_source_slide_draft._ensure_receipts"):
                with self.assertRaises(OfflineSlideDraftError):
                    create_draft(stage,root/"result")
            self.assertFalse((root/"result").exists())

    def test_existing_result_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=fixture(root)
            dest=root/"result"
            dest.mkdir()
            (dest/"user_note.txt").write_text("preserved")
            with self.assertRaises(OfflineSlideDraftError):
                create_draft(stage,dest)
            self.assertEqual((dest/"user_note.txt").read_text(),"preserved")

    def test_output_inside_original_stage_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=fixture(root)
            with self.assertRaises(OfflineSlideDraftError):
                create_draft(stage,stage/"bad_output")
            self.assertFalse((stage/"bad_output").exists())


if __name__=="__main__":
    unittest.main()
