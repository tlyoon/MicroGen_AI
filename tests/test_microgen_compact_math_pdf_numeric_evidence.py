"""Regression: exact short PDF math fragments count as visible numeric evidence."""
import unittest
from microgen_timed_cue_planner import (
    CuePlanningError, _pdf_text_blocks, _require_visible_numeric_evidence,
)
from microgen_cue_semantic_mapping import numbers


class _Rect:
    width = 360
    height = 280


class _Page:
    rect = _Rect()
    def get_text(self, mode):
        if mode != "blocks":
            raise ValueError("unsupported text mode")
        return [
            (310, -0.2, 338, 5, "18 / 21\n", 0, 0),
            (40, 45, 200, 60, "Substitute numerical values:\n", 1, 0),
            (150, 95, 210, 109, "3.00\n= 15.0 +\n", 2, 0),
            (212, 96, 275, 110, "255 = 31.0 s\n", 3, 0),
            (30, 130, 70, 140, "3 / 21\n", 4, 0),
            (30, 150, 43, 160, "45\n", 5, 0),
            (90, 160, 130, 170, "99 = 100\n", 6, 1),  # image block
        ]


class CompactNumericMathEvidence(unittest.TestCase):
    def test_exact_literal_short_math_passes_numeric_cue(self):
        blocks = _pdf_text_blocks(_Page())
        labels = [x[1] for x in blocks]
        self.assertIn("3.00\n= 15.0 +", labels)
        self.assertIn("255 = 31.0 s", labels)
        self.assertNotIn("18 / 21", labels)
        self.assertNotIn("99 = 100", labels)
        _require_visible_numeric_evidence(
            18, ["The visible expression equals 15.0 plus square root "
                 "of 255, which is 31.0 seconds."], blocks)

    def test_absent_derived_number_still_fails(self):
        blocks = _pdf_text_blocks(_Page())
        with self.assertRaisesRegex(CuePlanningError,
                                    "UNATTESTED_VISIBLE_NUMERIC_CUE"):
            _require_visible_numeric_evidence(18, [
                "The result equals 999.0 seconds."], blocks)


if __name__ == "__main__":
    unittest.main()
