"""PR272: source-constrained slide corrections and immutable QA rollback."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock
import fitz
import microgen_autonomous_science_qa as science
import microgen_autonomous_slide_repair as slide
from test_microgen_autonomous_science_qa import make_stage, approved, SOURCE_QUOTE


OLD = "Velocity of an object"
NEW = SOURCE_QUOTE


def make_correctable_stage(root):
    stage=make_stage(root)
    # Replace synthetic deck with a unique target slide text, not a duplicate
    # on both slides, so a one-slide adjustment can be proven.
    pdf=fitz.open()
    for i,text in enumerate((OLD,"Units of motion"),1):
        page=pdf.new_page()
        page.insert_text((30,80),text)
        page.insert_text((30,100),f"{i} / 2")
    pdf.save(stage/"slides_new.pdf")
    pdf.close()
    (stage/"slides_new.pdf").replace(stage/"slides.pdf")
    (stage/"slides.tex").write_text(
        r"\\begin{frame}"+OLD+r"\\end{frame}",encoding="utf8")
    return stage


def model_error():
    return {"slide":1,"status":"error","issues":[{
      "field":"slide","observed_quote":OLD,"source_quote":NEW,
      "suggested_replacement":NEW,
    }]}


class AutonomousSlideRepairTest(unittest.TestCase):
    def test_plain_text_only(self):
        for value in (
            r"\\frac{1}{2}", "$v=5$", "x_{1}", "v%bad",
            "bad\nline", "tiny"):
            with self.subTest(value=value):
                self.assertFalse(slide._safe_text(value))

    def test_rejected_unsafe_math_without_touching_files(self):
        with tempfile.TemporaryDirectory() as td:
            stage=make_correctable_stage(Path(td))
            before=science._inputs(stage)
            bad=model_error()
            bad["issues"][0]["observed_quote"]=r"\\frac{1}{2}"
            with self.assertRaises(science.ScienceQAError):
                science.audit_stage(stage,reviewer=lambda *_:{
                  "reviews":[bad,approved(2)]})
            self.assertEqual(before,science._inputs(stage))
            self.assertFalse((stage/science.RECEIPT).exists())

    def test_stale_implementation_receipt_is_archived_not_approved(self):
        with tempfile.TemporaryDirectory() as td:
            stage=make_correctable_stage(Path(td))
            def pass_all(*_):
                return {"reviews":[approved(1),approved(2)]}
            first=science.audit_stage(stage,reviewer=pass_all)
            self.assertEqual(first["source_bound_slide_text_corrections"],0)
            old=stage/science.RECEIPT
            stale=json.loads(old.read_text(encoding="utf8"))
            stale["implementation_sha256"]["science_qa"]="obsolete_qa_code"
            old.write_text(json.dumps(stale),encoding="utf8")
            with self.assertRaises(science.ScienceQAError):
                science.verify_receipt(stage)
            second=science.audit_stage(stage,reviewer=pass_all)
            self.assertEqual(second["status"],"SOURCE_GROUNDED_MODEL_SCREEN_PASSED")
            self.assertEqual(len(list(stage.glob(
                ".microgen_science_qa_prior_*.json"))),1)

    def test_safe_rendered_slide_replacement_gets_second_review(self):
        with tempfile.TemporaryDirectory() as td:
            stage=make_correctable_stage(Path(td))
            calls=[]
            def review(source, slide_pages, items):
                calls.append(slide_pages[:])
                return {"reviews":[model_error() if len(calls)==1
                          else approved(1),approved(2)]}
            def fake_renderer(folder,index,old,new,out):
                self.assertEqual(folder,stage)
                self.assertEqual(index,1)
                self.assertEqual((old,new),(OLD,NEW))
                tex=out/"slides.tex"
                tex.write_text((stage/"slides.tex").read_text().replace(OLD,NEW),
                               encoding="utf8")
                pdf=fitz.open()
                for i,text in enumerate((NEW,"Units of motion"),1):
                    page=pdf.new_page()
                    page.insert_text((30,80),text)
                    page.insert_text((30,100),f"{i} / 2")
                pdf.save(out/"slides.pdf")
                pdf.close()
                return tex,out/"slides.pdf",[NEW+"\n1 / 2\n",
                                              "Units of motion\n2 / 2\n"]
            with mock.patch(
                "microgen_autonomous_slide_repair.candidate_slide_edit",
                side_effect=fake_renderer
            ):
                receipt=science.audit_stage(stage,reviewer=review)
            self.assertEqual(len(calls),2)
            self.assertIn(NEW,calls[1][0])
            self.assertEqual(receipt["source_bound_slide_text_corrections"],1)
            self.assertEqual(receipt["source_bound_narration_corrections"],0)
            self.assertIn(NEW,(stage/"slides.tex").read_text())
            with fitz.open(stage/"slides.pdf") as final:
                self.assertIn(NEW,final[0].get_text())
                self.assertIn("Units of motion",final[1].get_text())
            self.assertEqual(science.verify_receipt(stage)["slide_count"],2)

    def test_reviewer_rejects_candidate_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as td:
            stage=make_correctable_stage(Path(td))
            before=science._inputs(stage)
            def deny(*_):
                return {"reviews":[model_error(),approved(2)]}
            # Fail during candidate compile, before mutation. No review retry
            # may forge acceptance even if the source quote exists.
            with mock.patch(
                "microgen_autonomous_slide_repair.candidate_slide_edit",
                side_effect=slide.SlideRepairError("Unsafe candidate")
            ):
                with self.assertRaises(science.ScienceQAError):
                    science.audit_stage(stage,reviewer=deny)
            self.assertEqual(science._inputs(stage),before)
            self.assertFalse((stage/science.RECEIPT).exists())
            self.assertEqual(len(list(stage.glob(
                ".microgen_science_qa_blocked_*.json"))),1)


if __name__ == "__main__":
    unittest.main()
