"""Synthetic-figure regression: no textbook assets in public test fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_teaching_slide_render import render_teaching_candidate
from test_microgen_source_teaching_slide_render import prepare
from microgen_serway_figure_panel_audit import inspect_serway_figure,FigurePanelError

def fixture(root):
    stage,qa,visual=prepare(root)
    source=stage/"source.pdf"
    doc=fitz.open(source)
    doc[1].insert_textbox(fitz.Rect(40,280,580,380),
        "Figure 1.1 (a) International Prototype of the Kilogram; "
        "(b) A cesium fountain atomic clock.",fontsize=11)
    replacement=root/"repaired_source.pdf"
    doc.save(replacement);doc.close();replacement.replace(source)
    figure=stage/"Figure 1.1.png"
    im=Image.new("RGB",(160,140),"white")
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,79,130),fill="red")
    d.rectangle((80,0,159,139),fill="blue")
    im.save(figure)
    receipt=json.loads(qa.read_text())
    receipt["source_pdf_sha256"]=sha_file(source)
    receipt["slides"][4]["narration"]="The left panel displays mass. The right panel shows an atomic clock."
    qa.write_text(json.dumps(receipt))
    plan=json.loads(visual.read_text())
    plan["slides"][4]["bullets"]=[
        "Panel (a): historical kilogram prototype",
        "Panel (b): cesium fountain atomic clock",
        "Two reproducible measurement references"]
    visual.write_text(json.dumps(plan))
    render_teaching_candidate(stage,qa,visual,root/"slides")
    pdf=root/"slides"/"slides_teaching_candidate.pdf"
    audit=root/"claims.json"
    audit.write_text(json.dumps({
        "status":"EIGHT_CRITICAL_SOURCE_CLAIM_GROUPS_SPOT_CHECKED",
        "source_pdf_sha256":sha_file(source),
        "narration_qa_sha256":sha_file(qa),
        "teaching_slides_sha256":sha_file(pdf),
        "publication_allowed":False}))
    return stage,root/"slides",qa,audit

class PanelAuditTests(unittest.TestCase):
    def test_caption_and_both_pixel_panels_match_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            stage,slides,qa,claims=fixture(Path(td))
            h=sha_file(stage/"Figure 1.1.png")
            result=inspect_serway_figure(stage,slides,qa,claims)
            self.assertEqual(len(result["panels"]),2)
            self.assertTrue(all(row["normalised_rgb_difference"]==0 for row in result["panels"]))
            self.assertFalse(result["full_figure_object_semantics_automatically_proven"])
            self.assertFalse(result["publication_allowed"])
            self.assertEqual(sha_file(stage/"Figure 1.1.png"),h)

    def test_figure_source_hash_drift_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,slides,qa,claims=fixture(Path(td))
            with (stage/"Figure 1.1.png").open("ab") as f:f.write(b"wrong")
            with self.assertRaises(FigurePanelError):
                inspect_serway_figure(stage,slides,qa,claims)

    def test_missing_caption_or_wrong_narration_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,slides,qa,claims=fixture(Path(td))
            n=json.loads(qa.read_text())
            n["slides"][4]["narration"]="No panel information available"
            qa.write_text(json.dumps(n))
            with self.assertRaises(FigurePanelError):
                inspect_serway_figure(stage,slides,qa,claims)

if __name__=="__main__":unittest.main()
