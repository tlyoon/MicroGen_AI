"""Known real 2.5 'y-value' -> 'yay' mispronunciation regression."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import microgen_pronunciation
import microgen_tts_acoustic_qa as qa
import text_to_speech_v25 as tts


SLIDE10 = (
    "Because continuous graphs have no breaks, they possess a powerful global "
    "property described by the Intermediate Value Theorem. It states that if "
    "a continuous function travels from one y-value to another over a closed "
    "interval, it must pass through every single y-value in between. "
    "It cannot skip over anything. If the function had a jump discontinuity, "
    "it could easily miss intermediate values, but a genuinely continuous "
    "function remains solidly connected."
)


class LetterNameTests(unittest.TestCase):
    def test_real_slide_10_both_occurrences_spoken_as_why_value(self):
        spoken = tts.normalize_scientific_speech(SLIDE10)
        self.assertEqual(spoken.count("why value"), 2)
        self.assertNotIn("y-value", spoken)
        self.assertIn("Intermediate Value Theorem", spoken)
        self.assertEqual(spoken, tts.normalize_scientific_speech(spoken))
        microgen_pronunciation.require_safe_speech(SLIDE10, spoken)
        self.assertEqual(SLIDE10.count("y-value"), 2)

    def test_compound_letter_names_typographic_variants(self):
        mapping = {
            "the y-value": "the why value",
            "the Y-value": "the why value",
            "two y-values": "two why values",
            "x-axis and y-axis": "ex axis and why axis",
            "X-intercept or Y-intercept": "ex intercept or why intercept",
            "the y-coordinate": "the why coordinate",
            "y\u2011component": "why component",
            "x \u2013 axis": "ex axis",
            "x-axes and y-axes": "ex axes and why axes",
        }
        for raw, expected in mapping.items():
            with self.subTest(raw=raw):
                self.assertEqual(tts.normalize_scientific_speech(raw), expected)

    def test_regular_english_and_other_abbreviations_untouched(self):
        untouched = [
            "Yesterday was sunny.", "The Y-shaped path split.",
            "We play yay on the team.", "Yale University.",
            "x-ray imaging", "Why do continuous functions matter?",
            "Take vitamin C. Next, read the appendix.",
            "The discovery dates to c. 1900.",
            "Use xylene as the solvent.",
            "The y-axis",  # this one is intentionally *not* untouched
        ]
        for raw in untouched[:-1]:
            with self.subTest(raw=raw):
                self.assertEqual(tts.normalize_scientific_speech(raw), raw)

    def test_same_voice_primary_tts_gets_normalized_y(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"candidate.wav"
            received=[]
            with patch.object(tts,"_google_synthesize",
                              side_effect=lambda spoken, target: received.append(spoken) or "google_cloud_chirp3"):
                provider=tts.synthesize(SLIDE10,path)
            self.assertEqual(provider,"google_cloud_chirp3")
            self.assertEqual(len(received),1)
            self.assertEqual(received[0].count("why value"),2)

    def test_asr_yay_vs_why_flagged_even_if_below_five_percent(self):
        expected=tts.normalize_scientific_speech(SLIDE10)
        heard=expected.replace("why value","yay value")
        mismatch=qa.mismatch_details(expected,heard)
        self.assertLess(mismatch["difference_fraction_upper_bound"],0.05)
        self.assertEqual(mismatch["letter_y_yay_red_flags"],2)

    def test_legitimate_why_not_mistaken_for_yay(self):
        self.assertEqual(qa.mismatch_details("why value","why value")["letter_y_yay_red_flags"],0)
        self.assertEqual(qa.mismatch_details("y-value","y-value")["letter_y_yay_red_flags"],0)


if __name__=="__main__":
    unittest.main()
