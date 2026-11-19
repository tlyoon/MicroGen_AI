"""Normal acoustic path regression: mixed evidence is not six proven errors.

Source-free recreation of the 10 Nov 2026 Serway 2.5 review pattern.
The existing two-slide repair budget and math/letter safeguards remain intact.
"""
from pathlib import Path
import unittest

import microgen_autonomous_acoustic_gate as gate


def report(slide_count=17, risk=(), disagreement=(), candidates=(), other=()):
    rows=[]
    risk=set(risk)
    disagreement=set(disagreement)
    candidates=set(candidates)
    other=set(other)
    for i in range(1,slide_count+1):
        status="ASR_SCREEN_PASS_LISTENING_REQUIRED"
        if i in risk:
            status="REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK"
        elif i in disagreement:
            status="REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE"
        elif i in candidates:
            status="REVIEW_REQUIRED_PRONUNCIATION_RISK"
        elif i in other:
            status="REVIEW_REQUIRED_UNCLEAR_SPEECH"
        rows.append({
            "slide":i,
            "assessment":status,
            "source_pronunciation_risks":([{"code":"standalone_math_letter"}]
                                           if i in risk else []),
        })
    return {
        "slides":rows,
        "review_required_slides":[r["slide"] for r in rows
            if r["assessment"]!="ASR_SCREEN_PASS_LISTENING_REQUIRED"],
        "unavailable_recognizer_passes":[],
    }


class MixedReviewRootCauseRegression(unittest.TestCase):
    def test_six_slide_historical_pattern_is_not_six_repairable_defects(self):
        r=report(risk=(10,17),disagreement=(11,12),candidates=(13,14))
        result=gate._classify_review_blocker(r)
        self.assertEqual(result["root_cause_family"],
                         "SOURCE_PRONUNCIATION_RISK_HOLD")
        self.assertEqual(result["review_categories"]["source_pronunciation_risk"],
                         [10,17])
        self.assertEqual(result["review_categories"]["transcriber_disagreement"],
                         [11,12])
        self.assertEqual(result["review_categories"]["repair_candidate"],[13,14])
        self.assertFalse(result["safe_auto_repair"])
        calls=[]
        def synthesize(*args,**kwargs):
            calls.append("unsafe paid audio render")
        with self.assertRaisesRegex(gate.AutonomousAcousticError,
                                    "SOURCE_PRONUNCIATION_RISK_HOLD"):
            gate._repair(Path("not-existing"),r,["source safe"]*17,
                         (lambda _: "",lambda _: ""),
                         synthesize=synthesize)
        self.assertEqual(calls,[])

    def test_two_genuinely_eligible_candidates_preserve_old_bounded_remedy(self):
        r=report(slide_count=3,candidates=(2,3))
        outcome=gate._classify_review_blocker(r)
        self.assertTrue(outcome["safe_auto_repair"])
        self.assertEqual(outcome["max_repair_slides"],2)
        self.assertEqual(outcome["review_categories"]["repair_candidate"],[2,3])

    def test_more_than_two_repairable_candidates_hold_without_paid_render(self):
        r=report(slide_count=5,candidates=(1,2,3))
        result=gate._classify_review_blocker(r)
        self.assertEqual(result["root_cause_family"],"REPAIR_CANDIDATE_BUDGET_HOLD")
        with self.assertRaisesRegex(gate.AutonomousAcousticError,
                                    "REPAIR_CANDIDATE_BUDGET_HOLD"):
            gate._repair(Path("not-existing"),r,["words"]*5,
                         (lambda _: "",lambda _: ""),
                         synthesize=lambda *_:self.fail("unbounded TTS called"))

    def test_ambiguous_review_cannot_consume_repair_budget(self):
        r=report(slide_count=4,disagreement=(2,),candidates=(3,4))
        classification=gate._classify_review_blocker(r)
        self.assertEqual(classification["root_cause_family"],"ASR_DISAGREEMENT_HOLD")
        self.assertFalse(classification["safe_auto_repair"])

    def test_unknown_issue_fails_closed(self):
        r=report(slide_count=3,other=(2,))
        classification=gate._classify_review_blocker(r)
        self.assertEqual(classification["root_cause_family"],
                         "AMBIGUOUS_ACOUSTIC_EVIDENCE_HOLD")
        self.assertFalse(classification["safe_auto_repair"])

    def test_invalid_or_reordered_ids_fail_before_any_providers(self):
        r=report(slide_count=3,candidates=(2,))
        r["slides"][1]["slide"]=1
        with self.assertRaisesRegex(gate.AutonomousAcousticError,
                                    "Acoustic report slide order mismatch"):
            gate._classify_review_blocker(r)


if __name__=="__main__":
    unittest.main()
