"""Offline adversarial tests for math TTS preflight (no API or source writes)."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import microgen_pronunciation as check
import text_to_speech_v25 as tts


class PreflightTests(unittest.TestCase):
    def test_thomas_2_5_all_four_cdot_cases_pass_after_normalizing(self):
        slide5 = "The limit is equal to the function's value, f of c. We can also define one-sided continuity."
        slide6 = ("At any point c. First, the function must actually be defined at c. "
                  "Second, a mathematical limit must exist as x approaches c. And third, compare the values.")
        for raw in (slide5, slide6):
            with self.subTest(raw=raw):
                check.require_safe_speech(raw, tts.normalize_scientific_speech(raw))
        self.assertEqual(tts.normalize_scientific_speech(slide5).count("see."), 1)
        self.assertEqual(tts.normalize_scientific_speech(slide6).count("see."), 3)

    def test_nearby_math_cdot_not_covered_by_replacement_blocks(self):
        cases = (
            "The limit tends to c. Then the graph is continuous.",
            "We approach a value c. Then proceed.",
            "Let the function converge to c. Next evaluate it.",
        )
        for raw in cases:
            spoken = tts.normalize_scientific_speech(raw)
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(check.PronunciationPreflightError, "ambiguous_math_c_period"):
                    check.require_safe_speech(raw, spoken)

    def test_nonmath_circa_dates_initials_and_labels_unchanged(self):
        for raw in (
            "Dated c. 1900.", "A parcel from c. 1800 was found.",
            "C. Smith wrote it.", "See Appendix C. Next, continue.",
            "Vitamin C. Great news.", "The entry c. Next comes d.",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(tts.normalize_scientific_speech(raw), raw)
                check.require_safe_speech(raw, raw)

    def test_safe_greek_and_comparison_normalization(self):
        self.assertEqual(
            tts.normalize_scientific_speech("α ≤ β ≠ γ and θ ≥ λ as x → ∞"),
            "alpha less than or equal to beta not equal to gamma and theta greater than or equal to lambda as x → infinity",
        )
        self.assertEqual(tts.normalize_scientific_speech("μ φ ω 25°C"), "mu phi omega 25 degrees Celsius")

    def test_latex_not_silently_pronounced(self):
        for raw in (r"Calculate \sqrt{x}.", r"Evaluate \int f(x) dx.", r"Consider \alpha."):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(check.PronunciationPreflightError, "raw_latex_command"):
                    check.require_safe_speech(raw, tts.normalize_scientific_speech(raw))

    def test_subscript_must_be_reviewed(self):
        for raw in ("Let x_1 be initial position.", "Coefficient a_n is finite."):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(check.PronunciationPreflightError, "raw_subscript"):
                    check.require_safe_speech(raw, tts.normalize_scientific_speech(raw))

    def test_preflight_happens_before_provider_or_output_file_creation(self):
        with TemporaryDirectory() as td:
            output = Path(td) / "slide.wav"
            with patch.object(tts, "_google_synthesize") as service:
                with self.assertRaises(check.PronunciationPreflightError):
                    tts.synthesize("The limit tends to c. Next, proceed.", output)
            service.assert_not_called()
            self.assertFalse(output.exists())

    def test_audit_preserves_slide_number_and_is_read_only(self):
        slides = [
            {"slide": 5, "tts_text": "Defined at c. Next."},
            {"slide": 6, "tts_text": "The function tends to c. Then continue."},
        ]
        copy = [dict(s) for s in slides]
        found = check.audit_slide_items(slides, tts.normalize_scientific_speech)
        self.assertEqual([x["slide"] for x in found], [6])
        self.assertEqual(slides, copy)


if __name__ == "__main__":
    unittest.main()
