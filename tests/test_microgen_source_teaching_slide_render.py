import json
import tempfile
import unittest
from pathlib import Path
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_teaching_slide_render import render_teaching_candidate,SourceSlideRenderError
from test_microgen_offline_source_slide_draft import fixture

def prepare(root):
    stage=fixture(root)
    n={"status":"EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED",
       "source_pdf_sha256":sha_file(stage/"source.pdf"),
       "academic_accuracy_independently_verified":False,"publication_allowed":False,
       "slide_count":8,"slides":[{"slide":i,"source_page":1,
       "spoken_text_sha256":"f"*64} for i in range(1,9)]}
    plan={"schema_version":1,"slides":[{"slide":i,"title":f"Teaching concept {i}",
       "bullets":["A measured quantity has a consistent unit",
                  "Physical standards enable repeated measurements",
                  "Validate results against familiar physical scales"]}
                  for i in range(1,9)]}
    qa=root/"narration_qa.json";v=root/"visual_plan.json"
    qa.write_text(json.dumps(n));v.write_text(json.dumps(plan))
    return stage,qa,v

class RenderTests(unittest.TestCase):
    def test_real_pdf_renders_source_bound_bullets_figure_and_si_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,qa,plan=prepare(root)
            original=[sha_file(stage/p) for p in ("source.pdf","Figure 1.1.png")]
            result=render_teaching_candidate(stage,qa,plan,root/"output")
            self.assertEqual(result["slide_count"],8)
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["formal_voice_authorized"])
            with fitz.open(root/"output"/"slides_teaching_candidate.pdf") as doc:
                self.assertEqual(len(doc),8)
                self.assertGreaterEqual(len(doc[4].get_images()),1)
                self.assertIn("SI UPDATE",doc[3].get_text())
                self.assertIn("Teaching concept 2",doc[1].get_text())
            self.assertEqual([sha_file(stage/p) for p in ("source.pdf","Figure 1.1.png")],original)
            self.assertEqual(json.loads((root/"output"/"teaching_slide_receipt.json").read_text()),result)

    def test_missing_slide_or_unsafe_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,qa,plan=prepare(root)
            j=json.loads(plan.read_text());j["slides"].pop()
            plan.write_text(json.dumps(j))
            with self.assertRaises(SourceSlideRenderError):
                render_teaching_candidate(stage,qa,plan,root/"out")
            self.assertFalse((root/"out").exists())

    def test_reject_existing_output_and_source_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,qa,plan=prepare(root)
            output=root/"previous";output.mkdir()
            with self.assertRaises(SourceSlideRenderError):
                render_teaching_candidate(stage,qa,plan,output)
            self.assertTrue(output.exists())
            with (stage/"source.pdf").open("ab") as f:f.write(b"drift")
            with self.assertRaises(SourceSlideRenderError):
                render_teaching_candidate(stage,qa,plan,root/"out")

if __name__=="__main__":
    unittest.main()
