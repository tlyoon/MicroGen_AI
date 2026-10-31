import unittest
from microgen_neural_asr_advisory import check_terms,AdvisoryError

class AdvisoryTests(unittest.TestCase):
    def test_planck_plank_homophone_not_false_pronunciation_error(self):
        result=check_terms(4,["mass","kilogram","plank"])
        self.assertEqual(result["recognizer_key_terms_found"]["planck"],"plank")
        self.assertEqual(result["recognizer_unmatched_terms"],[])
        self.assertFalse(result["acoustic_pronunciation_independently_verified"])

    def test_missing_words_are_advisory_not_proven_error(self):
        result=check_terms(8,["density"])
        self.assertIn("iron",result["recognizer_unmatched_terms"])
        self.assertFalse(result["missing_recognizer_terms_prove_mispronunciation"])

    def test_vocabulary_aliases(self):
        self.assertEqual(check_terms(5,["prototype","clock","caesium"])["recognizer_unmatched_terms"],[])
        self.assertEqual(check_terms(2,["standards","metre","kilograms"])["recognizer_unmatched_terms"],[])

    def test_malformed_asr_refused(self):
        with self.assertRaises(AdvisoryError):check_terms(4,["mass",{"word":"kilogram"}])
        with self.assertRaises(AdvisoryError):check_terms(100,["mass"])

if __name__=="__main__":unittest.main()
