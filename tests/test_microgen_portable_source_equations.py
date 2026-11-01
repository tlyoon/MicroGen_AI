"""Tests for source-original vector equations and independent hash-bound geometry."""
import json
import tempfile
import unittest
from pathlib import Path
import pymupdf as fitz

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_source_equations import crop_sha, SourceEquationError
from microgen_portable_slide_render import render_portable_slides
from test_microgen_portable_lecture_pipeline import setup


def with_equation(root, *, corrupt_sha=False, boundary=False, add_figure=False):
    a = setup(root, with_figure=add_figure)
    source, manifest = a[0] / "source.pdf", a[3]
    with fitz.open(source) as pdf:
        page = pdf[0]
        page.insert_text((46, 300), "E = m c^2", fontsize=24)
        pdf.saveIncr()
    with fitz.open(source) as pdf:
        rect = pdf[0].search_for("E = m c^2")[0]
        bbox = [round(x, 3) for x in (rect.x0-2, rect.y0-2, rect.x1+2, rect.y1+2)]
        sha = crop_sha(pdf[0], fitz.Rect(bbox))
    obj = json.loads(manifest.read_text())
    obj["source_pdf_sha256"] = sha_file(source)
    obj["source_equations"] = [{
        "slide":3 if boundary else 2,
        "source_page":2 if boundary else 1,
        "source_bbox":bbox,
        "source_crop_sha256":("0"*64 if corrupt_sha else sha)
    }]
    manifest.write_text(json.dumps(obj))
    return a


class SourceVectorEquationTests(unittest.TestCase):
    def test_original_source_equation_survives_as_pdf_vector(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = with_equation(root)
            result = render_portable_slides(*a[:4], root/"out")
            self.assertFalse(result["mathematical_equation_semantics_proven"])
            eq = result["slides"][1]["source_vector_equation"]
            self.assertTrue(eq["original_pdf_vector_copied"])
            self.assertFalse(eq["mathematical_semantics_independently_verified"])
            with fitz.open(root/"out"/"slides_teaching_candidate.pdf") as doc:
                self.assertEqual(len(doc), 3)
                self.assertTrue(doc[1].get_xobjects())
                self.assertIn("E = m c^2", doc[1].get_text())

    def test_mismatched_source_crop_sha_cannot_be_rendered(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=with_equation(root,corrupt_sha=True)
            with self.assertRaises(SourceEquationError):
                render_portable_slides(*a[:4],root/"denied")
            self.assertFalse((root/"denied").exists())

    def test_crop_on_neighboring_section_page_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=with_equation(root,boundary=True)
            with self.assertRaises(SourceEquationError):
                render_portable_slides(*a[:4],root/"denied")

    def test_first_page_previous_section_equation_rejected(self):
        from microgen_portable_source_equations import checked_equations
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=setup(root)
            with fitz.open(a[0]/"source.pdf") as pdf:
                # The section marker begins below y=30 in the test PDF.
                pdf[0].insert_text((40,18),"Q = 1",fontsize=10)
                pdf.saveIncr()
            with fitz.open(a[0]/"source.pdf") as pdf:
                box=pdf[0].search_for("Q = 1")[0]
                spec={"slide":1,"source_page":1,"source_bbox":list(box),
                      "source_crop_sha256":crop_sha(pdf[0],box)}
                n=json.loads(a[1].read_text())
                m=json.loads(a[3].read_text())
                m["source_equations"]=[spec]
                with self.assertRaises(SourceEquationError):
                    checked_equations(pdf,m,n,set())

    def test_equation_figure_overlap_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=with_equation(root,add_figure=True)
            obj=json.loads(a[3].read_text())
            obj["source_equations"][0]["slide"]=3
            obj["source_equations"][0]["source_page"]=2
            a[3].write_text(json.dumps(obj))
            with self.assertRaises(SourceEquationError):
                render_portable_slides(*a[:4],root/"denied")


if __name__=="__main__":
    unittest.main()
