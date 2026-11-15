"""Source-free regression for real G3 compact-kinematics narration blocker.

Narration is already source-bound; only the voice rendering may change.
"""
import unittest

from microgen_reviewed_math_voice import reviewed_math_voice, voice_input_risk_status
from text_to_speech_v25 import normalize_scientific_speech


class SourceMathVoiceRecovery(unittest.TestCase):
    def test_explicit_kinematic_roles_have_reviewed_spoken_forms(self):
        examples = {
            "a-sub-x equals a-sub-x average": "ay sub ex equals ay sub ex average",
            "v-sub-x-final minus v-sub-x-initial": "vee sub ex final minus vee sub ex initial",
            "x-final equals x-initial": "ex final equals ex initial",
            "x f minus x i": "ex final minus ex initial",
            "two a x times x f": "two ay sub ex times ex final",
            "v x average": "vee sub ex average",
            "d v x d t": "dee vee sub ex over dee tee",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(reviewed_math_voice(source), expected)
                status = voice_input_risk_status(source, normalize_scientific_speech)
                self.assertEqual(status["unresolved_source_risk_count"], 0)

    def test_normal_prose_not_globally_changed(self):
        text = "A xylophone and the x factor; Figure 2.12 is described in the source."
        self.assertEqual(reviewed_math_voice(text), text)
        self.assertNotEqual(reviewed_math_voice("x-final equals x-initial"), text)

    def test_unreviewed_isolated_variable_still_fails_closed(self):
        status = voice_input_risk_status(
            "The equation x is not yet specified.", normalize_scientific_speech)
        self.assertGreater(status["unresolved_source_risk_count"], 0)

    def test_full_deck_speech_preflight_cannot_certify_audio(self):
        status = voice_input_risk_status(
            "Velocity v-sub-x-final equals v-sub-x-initial.",
            normalize_scientific_speech)
        self.assertEqual(status["unresolved_source_risk_count"], 0)
        self.assertFalse(status["phoneme_certified"])


if __name__ == "__main__":
    unittest.main()
