"""Bound repeated Beamer layout repair across attempts and later resumes."""
import json
import tempfile
import unittest
from pathlib import Path

from microgen_layout_retry_guard import (
    LayoutRetryGuard,LayoutRepairRepeated,prevent_repeated_paid_layout_retry)


def stage_dir(path):
    folder=Path(path)
    (folder/"source.pdf").write_bytes(b"immutable source")
    (folder/"slides.tex").write_text("source-backed lecture A",encoding="utf8")
    (folder/"gen_slides_v20.py").write_text("algorithm v1",encoding="utf8")
    (folder/"microgen_slide_reflow.py").write_text("reflow v1",encoding="utf8")
    (folder/"gen_slides_prompt_v20_hybrid.txt").write_text("prompt v1",encoding="utf8")
    return folder


class LayoutRepeatGuardTests(unittest.TestCase):
    def test_identical_tex_and_overflow_stop_after_one_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=stage_dir(tmp)
            tex=stage/"slides.tex"
            original=tex.read_bytes()
            guard=LayoutRetryGuard(tex)
            error="Severe LaTeX layout overflow: hbox 100.3703 pt"
            guard.reject_duplicate(error,1)
            self.assertEqual(list(stage.glob("layout_repeat_guard_*.json")),[])
            with self.assertRaisesRegex(LayoutRepairRepeated,"Stop this PDF"):
                guard.reject_duplicate(error,2)
            diagnostic_path=list(stage.glob("layout_repeat_guard_*.json"))
            self.assertEqual(len(diagnostic_path),1)
            info=json.loads(diagnostic_path[0].read_text())
            self.assertEqual(info["first_failed_attempt"],1)
            self.assertEqual(info["repeated_attempt"],2)
            self.assertFalse(info["publication_allowed"])
            self.assertNotIn("source_pdf",info)
            self.assertEqual(tex.read_bytes(),original)
            with self.assertRaisesRegex(LayoutRepairRepeated,"Refusing another paid"):
                prevent_repeated_paid_layout_retry(stage)

    def test_page_out_of_bounds_is_also_a_repeat_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=stage_dir(tmp)
            guard=LayoutRetryGuard(stage/'slides.tex')
            error='Slide PDF failed: blank=[], counters=[], out_of_bounds=[13]'
            guard.reject_duplicate(error,1)
            with self.assertRaises(LayoutRepairRepeated):
                guard.reject_duplicate(error,2)
            prevent_blocked=list(stage.glob('layout_repeat_guard_*.json'))
            self.assertEqual(len(prevent_blocked),1)
            self.assertEqual(json.loads(prevent_blocked[0].read_text())['status'],
                             'UNRESOLVED_IDENTICAL_SLIDE_LAYOUT_REPAIR')
            with self.assertRaises(LayoutRepairRepeated):
                prevent_repeated_paid_layout_retry(stage)

    def test_changed_tex_allows_another_repair_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=stage_dir(tmp)
            tex=stage/"slides.tex"
            guard=LayoutRetryGuard(tex)
            guard.reject_duplicate("same hbox overflow",1)
            tex.write_text("source preserving frame break in original lecture",
                           encoding="utf8")
            guard.reject_duplicate("same hbox overflow",2)
            self.assertEqual(list(stage.glob("layout_repeat_guard_*.json")),[])

    def test_changed_producer_or_source_releases_previous_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=stage_dir(tmp)
            guard=LayoutRetryGuard(stage/"slides.tex")
            guard.reject_duplicate("hbox 100pt",1)
            with self.assertRaises(LayoutRepairRepeated):
                guard.reject_duplicate("hbox 100pt",2)
            (stage/"gen_slides_prompt_v20_hybrid.txt").write_text(
                "prompt v2: general layout repair",encoding="utf8")
            prevent_repeated_paid_layout_retry(stage)
            (stage/"gen_slides_prompt_v20_hybrid.txt").write_text(
                "prompt v1",encoding="utf8")
            (stage/"source.pdf").write_bytes(b"different original source")
            prevent_repeated_paid_layout_retry(stage)

    def test_same_tex_but_distinct_error_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=stage_dir(tmp)
            guard=LayoutRetryGuard(stage/"slides.tex")
            guard.reject_duplicate("hbox 3.0",1)
            guard.reject_duplicate("hbox 4.0",2)
            self.assertEqual(list(stage.glob("layout_repeat_guard_*.json")),[])

    def test_without_existing_deck_does_not_block_initial_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            (stage/"source.pdf").write_bytes(b"new source")
            prevent_repeated_paid_layout_retry(stage)


if __name__=="__main__":
    unittest.main()
