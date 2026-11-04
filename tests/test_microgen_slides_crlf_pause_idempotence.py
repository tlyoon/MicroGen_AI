"""PR277: verify the REAL slide-generation cleanup function without API imports.

gen_slides_v20.py executes Gemini calls at import time. Extract only the
standalone pure function with ast to test the actual production implementation.
"""
import ast
from pathlib import Path
import re
import tempfile
import unittest


def production_cleanup():
    source=Path(__file__).resolve().parents[1]/"gen_slides_v20.py"
    module=ast.parse(source.read_text(encoding="utf8"))
    definition=next(node for node in module.body
        if isinstance(node,ast.FunctionDef) and node.name=="clean_pause_in_place")
    namespace={"Path":Path,"re":re}
    exec(compile(ast.Module(body=[definition],type_ignores=[]),
                 str(source),"exec"),namespace)
    return namespace["clean_pause_in_place"]


class PauseNewlineTests(unittest.TestCase):
    def test_crlf_cleanup_is_idempotent_after_three_passes(self):
        clean=production_cleanup()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"slides.tex"
            original=("\\documentclass{beamer}\r\n"
                      "\\begin{document}\r\n"
                      "\\begin{frame}\r\n"
                      "The limit is defined.\r\n"
                      "\\[\r\n"
                      "\\lim_{t \\to 0} f(t) = 1\r\n"
                      "\\]\r\n"
                      "\\end{frame}\r\n"
                      "\\end{document}\r\n").encode("utf8")
            target.write_bytes(original)
            for turn in (1,2,3,4):
                clean(str(target))
                result=target.read_bytes()
                self.assertEqual(result,original,msg=f"modified math at pass {turn}")
                self.assertNotIn(b"\r\r\n",result)
                self.assertNotIn(b"\n\n",result)

    def test_standalone_and_inline_pause_removed_only_once(self):
        clean=production_cleanup()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"slides.tex"
            original=("\\begin{frame}\r\n"
                      "\\pause[2]\r\n"
                      "\\item A \\pause B\r\n"
                      "\\[\r\n"
                      "a^2+b^2=c^2\r\n"
                      "\\]\r\n"
                      "\\end{frame}\r\n").encode("utf8")
            expected=("\\begin{frame}\r\n"
                      "\\item A  B\r\n"
                      "\\[\r\n"
                      "a^2+b^2=c^2\r\n"
                      "\\]\r\n"
                      "\\end{frame}\r\n").encode("utf8")
            target.write_bytes(original)
            clean(str(target))
            self.assertEqual(target.read_bytes(),expected)
            clean(str(target))
            self.assertEqual(target.read_bytes(),expected)

    def test_lf_newline_not_rewritten(self):
        clean=production_cleanup()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"slides.tex"
            original=b"\\begin{frame}\n\\[\nx^2=1\n\\]\n\\end{frame}\n"
            target.write_bytes(original)
            clean(str(target))
            clean(str(target))
            self.assertEqual(target.read_bytes(),original)

    def test_cr_only_preserved_exactly(self):
        clean=production_cleanup()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"slides.tex"
            original=b"\\begin{frame}\r\\[\rx^2=1\r\\]\r\\end{frame}\r"
            target.write_bytes(original)
            for _ in range(3):
                clean(str(target))
            self.assertEqual(target.read_bytes(),original)


if __name__=="__main__":
    unittest.main()
