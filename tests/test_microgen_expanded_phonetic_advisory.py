"""No-network ASR tests: only interpretation rules, no hosted recognizer."""
import unittest
from microgen_expanded_phonetic_advisory import annotate,ExpandedAsrError

class ExpandedPhoneticTests(unittest.TestCase):
    def test_planck_and_caesium_homophones_not_blockers(self):
        p=annotate(6,"The Planck constant is fundamental",["kilogram","plank","mass"])
        self.assertEqual(p["recognized_terms"]["planck"],"plank")
        self.assertEqual(p["unmatched_terms"],[])
        c=annotate(7,"The cesium atomic clock",["prototype","clock","caesium"])
        self.assertEqual(c["unmatched_terms"],[])
        self.assertTrue(c["ASR_errors_are_not_phonetic_proof"])

    def test_targeted_c_dot_circa_risk_without_false_certification(self):
        r=annotate(7,"The derivative \\dot{C} appears",["prototype","clock","cesium","circa"])
        self.assertIn("C_DOT_POSSIBLY_PRONOUNCED_CIRCA",r["targeted_phonetic_hazards"])
        self.assertTrue(r["ASR_errors_are_not_phonetic_proof"])

    def test_targeted_y_dot_yay_risk(self):
        r=annotate(10,"The term y dot is used",["time","interval","instant","yay"])
        self.assertIn("Y_DOT_POSSIBLY_PRONOUNCED_YAY",r["targeted_phonetic_hazards"])

    def test_no_risks_without_math_context(self):
        r=annotate(6,"The result circa 1900",["circa","yay","kilogram","plank","mass"])
        self.assertEqual(r["targeted_phonetic_hazards"],[])

    def test_missing_terms_are_not_pronunciation_proof(self):
        r=annotate(14,"Aluminum is less dense than iron",["density"])
        self.assertIn("iron",r["unmatched_terms"])
        self.assertTrue(r["ASR_errors_are_not_phonetic_proof"])

    def test_bad_audio_observations_rejected(self):
        with self.assertRaises(ExpandedAsrError):
            annotate(15,"source",["density"])
        with self.assertRaises(ExpandedAsrError):
            annotate(14,"source",[{"word":"density"}])

if __name__=="__main__":unittest.main()
