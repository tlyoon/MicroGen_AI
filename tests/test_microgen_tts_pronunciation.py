"""Offline regression coverage for TTS-only mathematical-variable pronunciation."""

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import text_to_speech_v25 as tts


class ScientificPronunciationTests(unittest.TestCase):
    def setUp(self):
        provider = patch.dict(tts.os.environ, {"MICROGEN_FORMAL_TTS_PROVIDER": "google_cloud"})
        provider.start()
        self.addCleanup(provider.stop)

    def test_thomas_continuity_section_2_5_reproductions(self):
        slide5 = (
            "The two-sided limit as x approaches c is exactly equal to "
            "the function's value, f of c. We can also define one-sided continuity."
        )
        slide6 = (
            "This gives us a test for continuity at any point c. "
            "First, the function must actually be defined at c. "
            "Second, a mathematical limit must exist as x approaches c. "
            "And third, the limit must equal the actual function value."
        )
        self.assertEqual(tts.normalize_scientific_speech(slide5).count("see."), 1)
        self.assertEqual(tts.normalize_scientific_speech(slide6).count("see."), 3)
        self.assertNotIn(" c.", tts.normalize_scientific_speech(slide5 + " " + slide6))
        # The source text stays intact: the fix is only for synthesis.
        self.assertIn("f of c.", slide5)
        self.assertIn("point c.", slide6)

    def test_mathematical_variable_at_text_end_and_idempotence(self):
        cases = {
            "Take the limit at c.": "Take the limit at see.",
            "Consider point c. Next we differentiate.": "Consider point see. Next we differentiate.",
            "Find the coefficient c. Then simplify.": "Find the coefficient see. Then simplify.",
            "At c. First, evaluate the function.": "At see. First, evaluate the function.",
            "The variable c. Now solve.": "The variable see. Now solve.",
        }
        for source, spoken in cases.items():
            with self.subTest(source=source):
                self.assertEqual(tts.normalize_scientific_speech(source), spoken)
                self.assertEqual(tts.normalize_scientific_speech(spoken), spoken)

    def test_circa_initials_and_nonmath_text_are_preserved(self):
        untouched = (
            "The artifact dates to c. 1900.",
            "It was made at c. 1900, according to the catalog.",
            "C. Smith wrote this.",
            "See Appendix C. Next, read the graph.",
            "Vitamin C. This is an antioxidant.",
            "The letter c. See the alphabet.",
            "Example c. next comes d.",
            "Compute the value at c. 1900 is a historical estimate.",
        )
        for text in untouched:
            with self.subTest(text=text):
                self.assertEqual(tts.normalize_scientific_speech(text), text)

    def test_existing_scientific_normalization_remains(self):
        spoken = tts.normalize_scientific_speech("The variable c. Next, 3 × 2 cm/s.")
        self.assertEqual(spoken, "The variable see. Next, 3 times 2 centimetres per second.")

    def test_primary_and_fallback_receive_identical_corrected_text(self):
        input_text = "Evaluate at c. Next, take the limit."
        calls = []
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "slide6.wav"
            with patch.object(tts, "_google_synthesize", side_effect=lambda text, dest: calls.append(("primary", text)) or "google_cloud_chirp3"):
                self.assertEqual(tts.synthesize(input_text, out), "google_cloud_chirp3")
            self.assertEqual(calls, [("primary", "Evaluate at see. Next, take the limit.")])

            calls.clear()
            def fail_primary(text, dest):
                calls.append(("primary", text))
                raise RuntimeError("test-only failure")

            def record_fallback(text, dest):
                calls.append(("fallback", text))
                return "sapi"

            with patch.dict(tts.os.environ, {"MICROVID_TTS_FALLBACK": "sapi"}), \
                 patch.object(tts, "_google_synthesize", side_effect=fail_primary), \
                 patch.object(tts, "_sapi_synthesize", side_effect=record_fallback), \
                 warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                self.assertEqual(tts.synthesize(input_text, out), "sapi")
            self.assertEqual(calls, [
                ("primary", "Evaluate at see. Next, take the limit."),
                ("fallback", "Evaluate at see. Next, take the limit."),
            ])


if __name__ == "__main__":
    unittest.main()
