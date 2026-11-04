"""Adversarial autonomous scientific QA: real PDF fixture, no Gemini calls."""
import json
import tempfile
from pathlib import Path
import unittest

import fitz

import microgen_autonomous_science_qa as sq
import microgen_batch
from microgen_quality import dependency_fingerprint


SOURCE_QUOTE = "The velocity is ten metres per second"
WRONG_QUOTE = "five metres per second"
CORRECT_QUOTE = "ten metres per second"


def make_stage(root: Path, *, wrong: bool = False) -> Path:
    stage = root / "chapter"
    stage.mkdir()
    source = fitz.open()
    source.new_page().insert_text((40, 50),
        SOURCE_QUOTE + " in the reference example.")
    source.save(stage / "source.pdf")
    source.close()
    deck = fitz.open()
    for i in (1, 2):
        page = deck.new_page()
        page.insert_text((30, 80), "Velocity of an object")
        page.insert_text((30, 100), f"{i} / 2")
    deck.save(stage / "slides.pdf")
    deck.close()
    (stage / "slides.tex").write_text(
        r"\\begin{document}\\end{document}", encoding="utf8")
    slide1 = ("The velocity is five metres per second" if wrong
              else SOURCE_QUOTE)
    slide2 = "The velocity is measured in metres per second"
    sidecar = {"slides": [
        {"slide":1,"title":"Velocity","narration":slide1,"tts_text":slide1},
        {"slide":2,"title":"Units","narration":slide2,"tts_text":slide2},
    ]}
    (stage/"script_tts.json").write_text(
        json.dumps(sidecar,ensure_ascii=False),encoding="utf8")
    (stage/"script.txt").write_text(
        f"**Slide 1 [10 sec]:\n{slide1}\n\n"
        f"**Slide 2 [10 sec]:\n{slide2}\n",encoding="utf8")
    (stage/"microgen_autonomous_science_qa.py").write_text(
        "pinned_code_revision",encoding="utf8")
    return stage


def approved(number: int) -> dict:
    return {"slide":number,"status":"pass","issues":[]}


def flagged(quote=WRONG_QUOTE, cited=CORRECT_QUOTE,
            replacement=CORRECT_QUOTE, field="narration"):
    return {"slide":1,"status":"error","issues":[{
        "field":field,"observed_quote":quote,
        "source_quote":cited,"suggested_replacement":replacement}]}


class AutonomousScientificQA(unittest.TestCase):
    def test_integration_order_runs_before_paid_tts_and_video(self):
        self.assertLess(microgen_batch.STAGES.index("narration"),
                        microgen_batch.STAGES.index("science_qa"))
        self.assertLess(microgen_batch.STAGES.index("science_qa"),
                        microgen_batch.STAGES.index("tts"))
        self.assertIn("science_qa",microgen_batch.GEMINI_STAGES)
        self.assertIn("science_qa",microgen_batch.build_parser().
                      _option_string_actions["--stop-after"].choices)

    def test_passes_without_human_approval_and_sha_binds_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp))
            report=sq.audit_stage(stage,
                reviewer=lambda *_:{"reviews":[approved(1),approved(2)]})
            self.assertEqual(report["status"],
                "SOURCE_GROUNDED_MODEL_SCREEN_PASSED")
            self.assertFalse(report["human_review_required_for_development"])
            self.assertFalse(report["scientific_correctness_fully_certified"])
            self.assertEqual(sq.verify_receipt(stage)["slide_count"],2)
            self.assertTrue(microgen_batch.stage_valid(
                stage,"science_qa",Path(tmp)/"dest"))
            before=dependency_fingerprint(stage,"science_qa")
            (stage/"script.txt").write_text(
                (stage/"script.txt").read_text()+"\nCHANGED",encoding="utf8")
            self.assertNotEqual(before,dependency_fingerprint(stage,"science_qa"))
            with self.assertRaises(sq.ScienceQAError):
                sq.verify_receipt(stage)

    def test_safe_source_verbatim_correction_with_second_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp),wrong=True)
            calls=[]
            def review(source, slides, items):
                calls.append(items[0]["narration"])
                if len(calls)==1:
                    return {"reviews":[flagged(),approved(2)]}
                return {"reviews":[approved(1),approved(2)]}
            receipt=sq.audit_stage(stage,reviewer=review)
            self.assertEqual(len(calls),2)
            self.assertEqual(receipt["source_bound_narration_corrections"],1)
            self.assertIn(CORRECT_QUOTE,
                json.loads((stage/"script_tts.json").read_text())["slides"][0]["tts_text"])
            self.assertNotIn(WRONG_QUOTE,(stage/"script.txt").read_text())
            self.assertEqual(sq.verify_receipt(stage)["slide_count"],2)

    def test_unsupported_or_unsafe_correction_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp),wrong=True)
            before=sq._inputs(stage)
            for issue in (
                    flagged(cited="Invented velocity",replacement="Invented velocity"),
                    flagged(field="slide"),
                    flagged(replacement="Unproven correction")):
                with self.subTest(issue=issue):
                    with self.assertRaises(sq.ScienceQAError):
                        sq.audit_stage(stage,reviewer=lambda *_:{"reviews":[
                            issue,approved(2)]})
                    self.assertEqual(sq._inputs(stage),before)
                    self.assertFalse((stage/sq.RECEIPT).exists())
                    blocked=list(stage.glob(".microgen_science_qa_blocked_*.json"))
                    self.assertEqual(len(blocked),1)
                    diagnostic=json.loads(blocked[0].read_text())
                    self.assertEqual(diagnostic["status"],
                        "SOURCE_GROUNDED_SCIENCE_SCREEN_BLOCKED")
                    self.assertFalse(diagnostic["accepted_for_tts"])

    def test_failed_second_review_rolls_back_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp),wrong=True)
            before=sq._inputs(stage)
            times=[0]
            def reviewer(*_):
                times[0]+=1
                return {"reviews":[flagged(),approved(2)]}
            with self.assertRaises(sq.ScienceQAError):
                sq.audit_stage(stage,reviewer=reviewer)
            self.assertEqual(times[0],2)
            self.assertEqual(sq._inputs(stage),before)
            self.assertFalse((stage/sq.RECEIPT).exists())

    def test_rejects_missing_or_duplicate_slide_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp))
            for rows in ([approved(1)],
                         [approved(1),approved(1)],
                         [approved(2),approved(1)]):
                with self.subTest(rows=rows),self.assertRaises(sq.ScienceQAError):
                    sq.audit_stage(stage,reviewer=lambda *_,rows=rows:
                                   {"reviews":rows})
            self.assertFalse((stage/sq.RECEIPT).exists())

    def test_unresolved_slide_error_cannot_be_silently_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp))
            slide=flagged(quote="Velocity of an object",field="slide")
            with self.assertRaises(sq.ScienceQAError):
                sq.audit_stage(stage,reviewer=lambda *_:{"reviews":[slide,approved(2)]})
            self.assertFalse((stage/sq.RECEIPT).exists())

    def test_advisory_is_not_a_false_scientific_certification(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=make_stage(Path(tmp))
            advisory={"slide":1,"status":"advisory","issues":[{
                "field":"slide","observed_quote":"Velocity of an object",
                "source_quote":"","suggested_replacement":""}]}
            result=sq.audit_stage(stage,reviewer=lambda *_:{
                "reviews":[advisory,approved(2)]})
            self.assertEqual(result["advisory_slide_count"],1)
            self.assertFalse(result["scientific_correctness_fully_certified"])


if __name__ == "__main__":
    unittest.main()
