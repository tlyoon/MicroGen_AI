"""Bounded source formula + real-acoustic token correspondence contract."""
import unittest
from microgen_source_equation_audio_cues import (
    equation_candidates,EquationAnchorError,source_equation_lines
)
import pymupdf as fitz

CUBIC="In Example 10, the polynomial f of x equals x cubed minus x minus 1 is continuous."
ROOT="To show the square root of the quantity 2x plus 5 equals 4 minus x squared has a solution."
CUBIC_LINE={"text":"Example 10: For f (x) = x3 −x −1 on [1, 2]:",
            "box":[30.,80.,310.,100.]}
ROOT_LINE={"text":"Example 11: Prove that √2x + 5 = 4 −x2 has a solution.",
           "box":[30.,120.,310.,140.]}

def word(t,at,confidence=1):
    return {"word":t,"start":at,"end":at+.35,"conf":confidence}


class EquationCandidateContract(unittest.TestCase):
    def test_actual_cubic_math_phrase_timed_by_cubed(self):
        got=equation_candidates(CUBIC,[CUBIC_LINE],
            [word("equals",23.94),word("cubed",24.9)],duration=50.)
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["matched_source_formula_line"],CUBIC_LINE["text"])
        self.assertEqual(got[0]["box"],CUBIC_LINE["box"])
        self.assertFalse(got[0]["mathematical_equivalence_verified"])
        self.assertFalse(got[0]["equation_phrase_fully_synchronized"])

    def test_real_square_root_uses_only_first_qualified_root(self):
        words=[word("square",4.38),word("root",4.86),
               word("equals",8.01),word("square",15.33),
               word("root",15.78),word("equals",51.15)]
        cues=equation_candidates(ROOT,[ROOT_LINE],words,duration=53.)
        self.assertEqual(len(cues),1)
        self.assertAlmostEqual(cues[0]["start"],4.68)
        self.assertEqual(cues[0]["box"],ROOT_LINE["box"])

    def test_ambiguous_duplicate_equation_not_picked(self):
        got=equation_candidates(CUBIC,[CUBIC_LINE,CUBIC_LINE],
            [word("equals",23.94),word("cubed",24.9)],duration=50)
        self.assertEqual(got,[])

    def test_ambiguous_repeated_cubed_not_picked(self):
        got=equation_candidates(CUBIC,[CUBIC_LINE],
            [word("equals",20),word("cubed",21),word("equals",23),word("cubed",24)],
            duration=50)
        self.assertEqual(got,[])

    def test_no_math_narration_or_missing_asr_means_no_cues(self):
        self.assertEqual(equation_candidates("only a function",[CUBIC_LINE],
            [word("equals",1),word("cubed",2)],duration=5),[])
        self.assertEqual(equation_candidates(CUBIC,[CUBIC_LINE],[],duration=5),[])

    def test_wrong_pdf_line_or_low_confidence_not_promoted(self):
        bad=[{"text":"f(x)=x3+2","box":[30,40,300,50]}]
        self.assertEqual(equation_candidates(CUBIC,bad,
            [word("equals",1),word("cubed",2)],duration=5),[])
        self.assertEqual(equation_candidates(CUBIC,[CUBIC_LINE],
            [word("equals",1),word("cubed",2,.7)],duration=5),[])

    def test_invalid_asr_clock_fails_closed(self):
        for observations in ([word("cubed",9.8)], [{"word":"cubed","start":2,
              "end":float("nan"),"conf":1}]):
            with self.subTest(observations=observations):
                with self.assertRaises(EquationAnchorError):
                    equation_candidates(CUBIC,[CUBIC_LINE],observations,duration=5)

    def test_latex_like_text_does_not_claim_semantics(self):
        with fitz.open() as doc:
            page=doc.new_page(width=500,height=300)
            page.insert_text((30,60),"Example 10: f (x) = x3 -x -1")
            lines=source_equation_lines(page)
            self.assertTrue(any("x3" in x["text"] for x in lines))
            self.assertTrue(all(x["box"][0]>=0 for x in lines))


if __name__=="__main__":
    unittest.main()
