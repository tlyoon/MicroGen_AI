"""Fail-closed offline tests of immutable legacy Beamer PDF candidate repair."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_pdf_repair as repair


class LegacyBeamerRepairTests(unittest.TestCase):
    def test_explicit_shrink_changes_only_requested_frame(self):
        text = r"\begin{frame}{One}x\end{frame}" + "\n" + r"\begin{frame}{Two}y\end{frame}"
        actual = repair.patch_specific_frames(text, {2}, 5)
        self.assertIn(r"\begin{frame}[shrink=5]{Two}", actual)
        self.assertIn(r"\begin{frame}{One}", actual)
        self.assertNotIn("[shrink=5]{One}", actual)
        with self.assertRaisesRegex(repair.LegacyRepairError, "outside"):
            repair.patch_specific_frames(text, {3}, 5)
        with self.assertRaisesRegex(repair.LegacyRepairError, "between"):
            repair.patch_specific_frames(text, {1}, 30)

    def test_existing_options_require_manual_review(self):
        source = r"\begin{frame}[fragile]{Listing}abc\end{frame}"
        with self.assertRaisesRegex(repair.LegacyRepairError, "already has options"):
            repair.patch_specific_frames(source, {1}, 5)

    def test_refuse_overwrites_and_synced_drive_destinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "slides.tex").write_text(r"\begin{frame}{Hi}\end{frame}")
            (root / "slides.pdf").write_bytes(b"nonempty-placeholder")
            with self.assertRaisesRegex(repair.LegacyRepairError, "inside source"):
                repair.repair(root, root / "child")
            existing = root / "exists"
            existing.mkdir(exist_ok=True)
            with self.assertRaisesRegex(repair.LegacyRepairError, "already exists"):
                repair.repair(root, existing)
            with self.assertRaisesRegex(repair.LegacyRepairError, "LOCAL"):
                repair.repair(root, root.parent / "My Drive" / "candidate")

    def test_text_tokens_must_not_disappear(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            a = base / "old.pdf"
            b = base / "new.pdf"
            for file, text in ((a, "Necessary identity and denominator 2"),
                               (b, "Necessary identity and denominator")):
                doc = pymupdf.open()
                page = doc.new_page()
                page.insert_text((60, 80), text)
                doc.save(file)
                doc.close()
            with self.assertRaisesRegex(repair.LegacyRepairError, "words disappeared"):
                repair.compare_pages(a, b)

    def test_candidate_is_output_only_without_touching_original(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "course"
            source.mkdir()
            (source / "slides.tex").write_text(
                r"\documentclass{beamer}" + "\n"
                r"\begin{document}" + "\n"
                r"\begin{frame}{One}A\end{frame}" + "\n"
                r"\end{document}",
                encoding="utf-8"
            )
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((60, 40), "1 / 1")
            page.insert_text((60, 80), "A")
            doc.save(source / "slides.pdf")
            doc.close()
            original_tex = repair.sha(source / "slides.tex")
            original_pdf = repair.sha(source / "slides.pdf")
            output = root / "candidate"

            def fake_compile(staging, timeout):
                (staging / "slides.pdf").write_bytes((source / "slides.pdf").read_bytes())

            with mock.patch.object(repair, "compile_twice", side_effect=fake_compile):
                actual = repair.repair(source, output)
            self.assertEqual(actual["status"], "TECHNICAL_PDF_CANDIDATE_PASS")
            self.assertFalse(actual["publication_allowed"])
            self.assertTrue((output / "repair_report.json").exists())
            self.assertEqual(repair.sha(source / "slides.tex"), original_tex)
            self.assertEqual(repair.sha(source / "slides.pdf"), original_pdf)


if __name__ == "__main__":
    unittest.main()
