import copy
import tempfile
import unittest
from pathlib import Path
import microgen_tts_lexicon as lex
import text_to_speech_v25 as tts

class ReviewedLexiconTests(unittest.TestCase):
    def test_lexicon_validates_examples_and_negatives(self):
        data=lex.load_lexicon()
        self.assertEqual(data["schema_version"],1)
        self.assertEqual(len(data["reviewed_rules"]),2)
    def test_confirmed_y_and_c_rules_current_tts_satisfies(self):
        raw="The y-value is defined at c. Then examine the x-axis."
        self.assertEqual(lex.verify_spoken_rules(raw,tts.normalize_scientific_speech(raw)),[])
    def test_detects_normalizer_regression_not_false_pass(self):
        raw="The y-value is defined at c. Then continue."
        broken="The yay value is defined at circa. Then continue."
        found=lex.verify_spoken_rules(raw,broken)
        self.assertEqual(len(found),2)
        self.assertEqual({r["rule"] for r in found},{"xy-coordinate-compounds","sentence_math_cdot"})
    def test_regular_language_no_detection(self):
        raw="Yesterday was sunny, c. 1900, and Yale opened."
        self.assertEqual(lex.verify_spoken_rules(raw,raw),[])
    def test_lexicon_does_not_mutate_source_or_normalized_text(self):
        raw="At c. Next the y-value is plotted."
        a=tts.normalize_scientific_speech(raw)
        lex.verify_spoken_rules(raw,a)
        self.assertEqual(raw,"At c. Next the y-value is plotted.")
    def test_bad_version_and_overbroad_rule_fail_closed(self):
        original=lex.load_lexicon()
        bad=copy.deepcopy(original)
        bad["schema_version"]=1000
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.json"
            import json
            p.write_text(json.dumps(bad),encoding="utf8")
            with self.assertRaises(lex.LexiconError):
                lex.load_lexicon(p)
            bad=copy.deepcopy(original)
            bad["reviewed_rules"][0]["negative_examples"].append("y-value")
            p.write_text(json.dumps(bad),encoding="utf8")
            with self.assertRaises(lex.LexiconError):
                lex.load_lexicon(p)
    def test_lexicon_no_automatic_unreviewed_formula_expansion(self):
        data=lex.load_lexicon()
        self.assertIn("f(x)",[x["term"] for x in data["review_required"]])
        self.assertIn("μ",[x["term"] for x in data["review_required"]])
        self.assertEqual(lex.verify_spoken_rules("Evaluate f(x).","Evaluate f of ex.",lexicon=data),[])
