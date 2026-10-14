import tempfile
import unittest
from pathlib import Path
from unittest import mock
from microgen_slide_reflow import (
  FRAME_RX, _math_evidence, _set_total_if_provable,
  reflow_document, repair_layout,
)
from microgen_quality import sha256


EXAMPLE_DECK=r"""
\documentclass{beamer}
\setbeamertemplate{headline}{\insertframenumber{} / \inserttotalframenumber}
\begin{document}
\begin{frame}{Examples A and B}
\begin{exampleblock}{First}
Evaluate $\int x\,dx$:
\[\int x\,dx=\frac{x^2}{2}+C\]
\end{exampleblock}
\begin{exampleblock}{Second}
Evaluate $\int x^2\,dx$:
\[\int x^2\,dx=\frac{x^3}{3}+C\]
\end{exampleblock}
\end{frame}
\begin{frame}{Comparing Applications}
\textbf{Compare outputs}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\textbf{First method}
\[\int x\,dx=\frac{x^2}{2}+C\]
\end{column}
\begin{column}{0.48\textwidth}
\textbf{Second method}
\[\int x^2\,dx=\frac{x^3}{3}+C\]
\end{column}
\end{columns}
This is the concluding observation.
\end{frame}
\end{document}
"""


class LayoutReflowUnitTests(unittest.TestCase):
    def test_math_is_never_changed_by_example_reflow(self):
        candidates=reflow_document(EXAMPLE_DECK,"examples")
        self.assertEqual(len(candidates),1)
        txt,label,count=candidates[0]
        self.assertEqual(count,2)
        self.assertEqual(len(list(FRAME_RX.finditer(txt))),3)
        self.assertEqual(_math_evidence(txt),_math_evidence(EXAMPLE_DECK))
        self.assertIn(r"\frac{x^3}{3}",txt)

    def test_math_is_never_changed_by_column_reflow(self):
        candidates=reflow_document(EXAMPLE_DECK,"columns")
        self.assertEqual(len(candidates),1)
        txt,label,count=candidates[0]
        self.assertEqual(count,2)
        self.assertEqual(len(list(FRAME_RX.finditer(txt))),3)
        self.assertEqual(_math_evidence(txt),_math_evidence(EXAMPLE_DECK))
        self.assertIn("This is the concluding observation.",txt)

    def test_two_transforms_preserve_all_math(self):
        after_examples=reflow_document(EXAMPLE_DECK,"examples")[0][0]
        after_columns=reflow_document(after_examples,"columns")[0][0]
        self.assertEqual(len(list(FRAME_RX.finditer(after_columns))),4)
        self.assertEqual(_math_evidence(after_columns),_math_evidence(EXAMPLE_DECK))
        self.assertEqual(after_columns.count("This is the concluding observation."),1)

    def test_no_reflow_when_unsafe_nested_or_unsupported(self):
        text=EXAMPLE_DECK.replace(r"\end{frame}",r"\begin{frame}",1)
        self.assertEqual(reflow_document(text,"examples"),[])

    def test_total_stamps_only_plain_overlay_free_frames(self):
        expected=_set_total_if_provable(EXAMPLE_DECK)
        self.assertIn(r"\insertframenumber{} / 2",expected)
        self.assertNotIn(r"\inserttotalframenumber",expected)
        self.assertEqual(_set_total_if_provable(EXAMPLE_DECK+r"\pause"),EXAMPLE_DECK+r"\pause")

    def test_failed_candidates_leave_original_files_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            stage=Path(temp)
            path=stage/"slides.tex"
            pdf=stage/"slides.pdf"
            path.write_text(EXAMPLE_DECK,encoding="utf-8")
            pdf.write_bytes(b"existing-good-pdf")
            with mock.patch("microgen_slide_reflow._attempt_compile",
                            return_value=(False,"mock compile rejected",None)):
                result=repair_layout(path,max_candidates=3)
            self.assertEqual(result["status"],"not_repaired")
            self.assertEqual(path.read_text(encoding="utf-8"),EXAMPLE_DECK)
            self.assertEqual(pdf.read_bytes(),b"existing-good-pdf")

    def test_math_provenance_detects_deleted_equation(self):
        original=_math_evidence(EXAMPLE_DECK)
        mutated=EXAMPLE_DECK.replace(r"\int x^2\,dx=\frac{x^3}{3}+C",r"\int x^2\,dx=0")
        self.assertNotEqual(original,_math_evidence(mutated))


if __name__=="__main__":
    unittest.main()
