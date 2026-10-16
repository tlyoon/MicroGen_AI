"""Regression tests for academic QA warnings discovered in Thomas 8.4-8.6."""
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf
import microgen_quality as q


class NarrationTitleQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"slides.tex").write_text(
            r"\\title{8.5 Integration of Rational Functions by Partial Fractions}",
            encoding="utf-8",
        )

    def check(self,spoken, should_fail):
        human=self.root/"script.txt"
        sidecar=self.root/"script_tts.json"
        human.write_text(f"**Slide 1 [1 sec]:\n{spoken}**\n",encoding="utf-8")
        sidecar.write_text(json.dumps({"slides":[{"slide":1,"narration":spoken,"tts_text":spoken}]}),encoding="utf-8")
        if should_fail:
            with self.assertRaisesRegex(q.QualityError, "truncates"):
                q.check_narration(human,sidecar,1)
        else:
            self.assertEqual(q.check_narration(human,sidecar,1)["pages"],1)

    def test_truncated_course_title_rejected(self):
        self.check("8.5 Integration of Rational Functions by Partial",True)

    def test_complete_course_title_accepted(self):
        self.check("8.5 Integration of Rational Functions by Partial Fractions",False)

    def test_custom_intro_not_falsely_rejected(self):
        self.check("Welcome to rational function integration.",False)


class FigureVisibilityQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/"figures.pdf"

    def _make_pdf(self,rect):
        image=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,232,480),False)
        image.clear_with(255)
        png=image.tobytes("png")
        pdf=pymupdf.open()
        page=pdf.new_page(width=400,height=225)
        page.insert_image(pymupdf.Rect(*rect),stream=png)
        pdf.save(str(self.file))
        pdf.close()

    def test_tall_composite_shrunk_to_narrow_strip_flagged(self):
        self._make_pdf((12,20,38,75))
        flags=q.figure_display_warnings(self.file)
        self.assertEqual([item["slide"] for item in flags],[1])
        self.assertTrue(flags[0]["review_required"])

    def test_wide_legible_montage_not_flagged(self):
        self._make_pdf((12,20,335,110))
        self.assertEqual(q.figure_display_warnings(self.file),[])


if __name__=="__main__":
    unittest.main()
