"""Autonomous QA is strict about machines, optional about human approvals."""
import unittest
from microgen_tts_release_policy import (
    decide_release, QAPolicyError, TECHNICAL_GATES, HUMAN_APPROVALS,
)

class AutonomousPolicyTests(unittest.TestCase):
    def complete(self):
        return {key:True for key in TECHNICAL_GATES+HUMAN_APPROVALS}

    def test_all_technical_true_and_human_false_clear_autonomous_only(self):
        checks=self.complete()
        for role in HUMAN_APPROVALS:
            checks[role]=False
        decision=decide_release(checks)
        self.assertTrue(decision["ready_for_separate_promotion"])
        self.assertTrue(decision["automated_technical_qa_passed"])
        self.assertEqual(decision["human_reviews_pending"],list(HUMAN_APPROVALS))
        self.assertFalse(decision["human_qa_certified"])
        self.assertFalse(decision["publication_performed"])

    def test_every_missing_machine_gate_always_blocks(self):
        for key in TECHNICAL_GATES:
            with self.subTest(key=key):
                checks=self.complete()
                checks[key]=False
                result=decide_release(checks)
                self.assertFalse(result["automated_technical_qa_passed"])
                self.assertFalse(result["ready_for_separate_promotion"])
                self.assertIn(key,result["technical_blockers"])

    def test_human_certified_option_is_opt_in_not_silent_default(self):
        checks=self.complete()
        checks["all_slide_listening_approved"]=False
        self.assertTrue(decide_release(checks)["ready_for_separate_promotion"])
        strict=decide_release(checks,"human-certified")
        self.assertFalse(strict["ready_for_separate_promotion"])
        self.assertTrue(strict["manual_approval_is_gate"])
        self.assertIn("all_slide_listening_approved",strict["blockers"])

    def test_reject_invalid_or_incomplete_evidence(self):
        checks=self.complete()
        for candidate in ("manual-permissive","",None):
            with self.assertRaises(QAPolicyError):
                decide_release(checks,candidate)
        checks.pop("independent_acoustic_screen")
        with self.assertRaises(QAPolicyError):
            decide_release(checks)
        checks=self.complete()
        checks["voice_bound_wav_provenance"]=1
        with self.assertRaises(QAPolicyError):
            decide_release(checks)

    def test_truthful_evidence_class_in_both_modes(self):
        checks=self.complete()
        result=decide_release(checks)
        self.assertEqual(result["release_evidence_class"],
                         "HUMAN_CERTIFIED_AND_AUTOMATED_QA")
        self.assertTrue(result["human_qa_certified"])
        self.assertTrue(result["no_claim_of_human_review"] is False)
        checks["figures_review_approved"]=False
        self.assertEqual(decide_release(checks)["release_evidence_class"],
                         "AUTOMATED_TECHNICAL_QA_ONLY")
