"""Source-independent adversarial tests for production timed equation recovery."""
from __future__ import annotations
import copy
import unittest
import fitz
from microgen_source_math_cue import (
    build_exact_source_math_cue, exact_source_math_span,
    source_math_quote_valid, verified_source_math_row,
    math_signature,
)


class Page:
    rect = fitz.Rect(0, 0, 360, 260)
    def __init__(self, rows):
        self.rows = rows
    def get_textbox(self, box):
        selected = [
            row[1] for row in self.rows
            if (row[0][0] >= box.x0 - 0.01 and row[0][1] >= box.y0 - 0.01
                and row[0][2] <= box.x1 + 0.01
                and row[0][3] <= box.y1 + 0.01)
        ]
        return "\n".join(selected)


def fixture(labels, *, start=45, step=16):
    rows = []
    for i, label in enumerate(labels):
        box = [50.0, float(start+step*i), 305.0, float(start+step*i+11)]
        rows.append((box, label, set()))
    return rows, Page(rows)


class SourceMathCueAutoRecovery(unittest.TestCase):
    def test_actual_four_source_math_patterns(self):
        cases = [
            (["Mean of initial and final velocities.",
              "vx,avg = vxi + vxf", "2 (for constant ax)"],
             "The equation vee sub ex average equals vee sub ex initial "
             "plus vee sub ex final, divided by 2 for constant ay sub ex."),
            (["xf = xi + 1", "2(vxi + vxf )t (for constant ax)"],
             "Therefore, ex final equals ex initial plus one-half of vee "
             "sub ex initial plus vee sub ex final for constant ay sub ex."),
            (["vxf = vxi = vx and xf = xi + vxt"],
             "The equation v ex final equals v ex initial equals vee ex, "
             "and ex final equals ex initial plus vee sub ex times tee."),
            (["xf = xi + 1", "2(vxi + vxf)t = 0 + 1 "
              "2(63 m/s + 0)(2.0 s) = 63 m"],
             "Ex final equals ex initial plus one-half of vee ex initial "
             "plus vee ex final, times t gives 0 plus 63 times 2.0, "
             "which equals 63 meters."),
        ]
        for labels, spoken in cases:
            with self.subTest(labels=labels):
                blocks, page = fixture(labels)
                cue = build_exact_source_math_cue(5, 2, spoken, blocks, page)
                self.assertIsNotNone(cue)
                self.assertTrue(verified_source_math_row(cue, 5, 2, blocks, page))
                self.assertEqual(cue["source_math_evidence"], "EXACT_SOURCE_MATH_V1")

    def test_signed_or_unsupported_numeric_claim_is_not_approved(self):
        blocks, page = fixture([
            "xf = xi + 1", "2(vxi + vxf)t = 0 + 1 2(63+0)(2.0) = 63"
        ])
        spoken = ("Ex final equals ex initial plus vee ex initial "
                  "plus vee ex final, giving 999 meters.")
        self.assertIsNone(exact_source_math_span(spoken, blocks, page))

    def test_reversed_equation_and_changed_sign_fail(self):
        spoken = ("Ex final equals ex initial plus vee ex initial "
                  "plus vee ex final for constant ay sub ex.")
        for printed in ["xi = xf + 1", "xf = xi - 1"]:
            blocks, page = fixture([printed, "2(vxi + vxf)t for constant ax"])
            self.assertIsNone(exact_source_math_span(spoken, blocks, page))

    def test_duplicate_source_equations_abstain_as_ambiguous(self):
        labels = ["vx,avg = vxi + vxf", "2 (for constant ax)",
                  "Other printed explanation.",
                  "vx,avg = vxi + vxf", "2 (for constant ax)"]
        blocks, page = fixture(labels, step=20)
        spoken = ("Vee sub ex average equals vee sub ex initial plus vee "
                  "sub ex final divided by 2 for constant ay sub ex.")
        self.assertIsNone(exact_source_math_span(spoken, blocks, page))

    def test_out_of_bounds_region_is_never_approved(self):
        rows, page = fixture(["vxf = vxi = vx and xf = xi + vxt"])
        rows[0][0][2] = 390
        spoken = ("V ex final equals v ex initial equals vee ex, "
                  "and ex final equals ex initial plus vee ex times tee.")
        self.assertIsNone(exact_source_math_span(spoken, rows, page))

    def test_tampered_plan_fields_are_independently_rejected(self):
        blocks, page = fixture(["vxf = vxi = vx and xf = xi + vxt"])
        spoken = ("V ex final equals v ex initial equals vee ex, "
                  "and ex final equals ex initial plus vee ex times tee.")
        original = build_exact_source_math_cue(4, 1, spoken, blocks, page)
        self.assertTrue(verified_source_math_row(original, 4, 1, blocks, page))
        for field, false_value in [
            ("pdf_bbox", [0,0,15,15]),
            ("semantic_source_quote", "different equation"),
            ("source_math_evidence", "UNVERIFIED"),
            ("spoken_text", spoken.replace("ex final", "ex initial", 1)),
        ]:
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed[field] = false_value
                self.assertFalse(verified_source_math_row(
                    changed, 4, 1, blocks, page))

    def test_short_math_proof_does_not_allow_arbitrary_short_text(self):
        self.assertTrue(source_math_quote_valid("xf = xi + 1"))
        self.assertFalse(source_math_quote_valid("x=1"))
        self.assertFalse(source_math_quote_valid("123 = 45"))
        self.assertNotIn("xb", math_signature("A random toolbox.", spoken=False))


if __name__ == "__main__":
    unittest.main()
