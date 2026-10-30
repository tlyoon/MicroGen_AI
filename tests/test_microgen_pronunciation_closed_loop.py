"""General math speech + evidence-grounded selective repair regression."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import microgen_pronunciation_closed_loop as loop
from text_to_speech_v25 import normalize_scientific_speech as normalize
from microgen_pronunciation import require_safe_speech, PronunciationPreflightError


def words(text, wavhash):
    rows=[{"word":word,"start":float(i)*.1,"end":(i+1)*.1,"conf":.89}
          for i,word in enumerate(text.split())]
    return {"source_wav_sha256":wavhash,
            "words":rows,"phonetic_identity_verified":False,
            "semantic_word_alignment_certified":False}


class ClosedLoopPronunciationTests(unittest.TestCase):
    def test_generalized_math_grammar_expands_several_non_c_y_forms(self):
        self.assertEqual(
            normalize("Let f(x) = sin(x) + ln(y), and compare g(t) with x_1."),
            "Let eff of ex = sine of ex + natural logarithm of why, "
            "and compare gee of tee with ex subscript one."
        )
        self.assertEqual(normalize("Use cos(x), tan(y), h(t), z_9."),
                         "Use cosine of ex, tangent of why, aitch of tee, zee subscript nine.")
        self.assertEqual(normalize(normalize("Use cos(x), tan(y), h(t), z_9.")),
                         normalize("Use cos(x), tan(y), h(t), z_9."))
        require_safe_speech("Let x_1 be the point.",normalize("Let x_1 be the point."))

    def test_unsafe_composite_expressions_are_not_guessed(self):
        examples=("f(x+1)","sin(x+y)","x_12","a_n","arcsin(x)","text_x_1")
        for raw in examples:
            with self.subTest(raw=raw):
                self.assertEqual(normalize(raw), raw)
        with self.assertRaises(PronunciationPreflightError):
            require_safe_speech("Take a_n.",normalize("Take a_n."))

    def test_glossary_is_validated_and_rejects_overbroad_unreviewed_rules(self):
        self.assertEqual(len(loop.load_glossary()),3)
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"rules.json"
            content=json.loads(loop.DEFAULT_GLOSSARY.read_text(encoding="utf-8"))
            content["rules"][0]["regex"]=r"sin|cos"
            target.write_text(json.dumps(content),encoding="utf-8")
            with self.assertRaises(loop.PronunciationClosedLoopError):
                loop.load_glossary(target)

    def test_any_new_reviewed_technical_word_can_be_added_as_data_not_code(self):
        with tempfile.TemporaryDirectory() as temp:
            base=json.loads(loop.DEFAULT_GLOSSARY.read_text(encoding="utf-8"))
            # A synthetic fixture exercises the extension mechanism; it does
            # NOT claim this test pronunciation is independently approved.
            extra={
                "id":"test-only-technical-word",
                "safety":"conservative_math_notation",
                "replacement_kind":"technical_term",
                "regex":r"\bRiemann\b",
                "spoken_form":"ree mahn",
                "reviewed_evidence_sha256":"a"*64,
                "case_insensitive":False,
                "examples":["Riemann integral"],
                "negative_examples":["Riemannian manifold","Friedmann"],
            }
            base["rules"].append(extra)
            p=Path(temp)/"test_glossary.json"
            p.write_text(json.dumps(base),encoding="utf-8")
            patterns=loop.load_glossary(p)
            self.assertEqual(
                loop.expand_unambiguous_math("Riemann integral",glossary=patterns),
                "ree mahn integral")
            self.assertEqual(
                loop.expand_unambiguous_math("Riemannian manifold",glossary=patterns),
                "Riemannian manifold")
            extra.pop("reviewed_evidence_sha256")
            p.write_text(json.dumps(base),encoding="utf-8")
            with self.assertRaises(loop.PronunciationClosedLoopError):
                loop.load_glossary(p)

    def test_screen_real_sha_bound_circa_yay_and_harmless_sea(self):
        wavhash="a"*64
        raw=loop.screen_audio("Evaluate at see. Next take the limit.",
                              words("evaluate at circa next take the limit",wavhash),wavhash)
        good=loop.screen_audio("Evaluate at see. Next take the limit.",
                               words("evaluate at sea next take the limit",wavhash),wavhash)
        self.assertEqual([r["code"] for r in raw["high_confidence_flags"]],
                         ["math_letter_c_circa"])
        self.assertEqual(good["high_confidence_flags"],[])
        self.assertEqual(good["word_mismatches"],[])
        self.assertFalse(good["acoustic_approved"])
        y=loop.screen_audio("the why value changes",
                            words("the yay value changes",wavhash),wavhash)
        self.assertEqual(y["high_confidence_flags"][0]["code"],"math_letter_y_yay")

    def test_audio_mismatch_outside_known_pattern_is_not_autofixed(self):
        h="a"*64
        bad=loop.screen_audio("the function is continuous",
                              words("the fraction is continuous",h),h)
        self.assertFalse(bad["high_confidence_flags"])
        self.assertTrue(bad["word_mismatches"])
        self.assertFalse(bad["acoustic_approved"])

    def test_audio_bad_word_elsewhere_is_not_misattributed(self):
        h="f"*64
        audit=loop.screen_audio("at see the circa number",
            words("at sea the circa number",h),h)
        self.assertEqual(audit["high_confidence_flags"],[])

    def test_reject_tampered_or_false_certified_asr(self):
        h="a"*64
        bad=words("evaluate at circa",h)
        with self.assertRaises(loop.PronunciationClosedLoopError):
            loop.screen_audio("evaluate at see",bad,"b"*64)
        bad["phonetic_identity_verified"]=True
        with self.assertRaises(loop.PronunciationClosedLoopError):
            loop.screen_audio("evaluate at see",bad,h)

    def test_slide_plan_selects_only_known_affected_slide(self):
        h="b"*64
        slides=[
            {"slide":5,"tts_text":"Evaluate at c. Next, take the limit."},
            {"slide":6,"tts_text":"Compute the area of the rectangle."},
        ]
        raw1=words("evaluate at circa next take the limit",h)
        clean2=words("compute the area of the rectangle",h)
        before=json.dumps(slides)
        result=loop.plan_slide_repairs(slides,normalize,
            observations=[raw1,clean2],wav_hashes=[h,h])
        self.assertEqual(result["selective_diagnostic_slides"],[5])
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(json.dumps(slides),before)
        self.assertTrue(result["slides"][0]["bounded_diagnostic_candidate"])
        self.assertFalse(result["slides"][1]["bounded_diagnostic_candidate"])
        self.assertEqual(result["slides"][0]["tts_text"],
                         "Evaluate at see. Next, take the limit.")

    def test_without_audio_uses_text_only_and_never_certifies(self):
        plan=loop.plan_slide_repairs([
            {"slide":1,"tts_text":"Compute f(x) and sin(x)."}],normalize)
        self.assertFalse(plan["phonetic_identity_verified"])
        self.assertEqual(plan["selective_diagnostic_slides"],[])
        self.assertEqual(plan["slides"][0]["screening"]["status"],"AUDIO_NOT_SCREENED")
        self.assertTrue(plan["slides"][0]["text_was_normalized"])

    def test_bounded_cloud_diagnostic_only_regenerates_evidence_backed_slide(self):
        h="b"*64
        slides=[{"slide":5,"tts_text":"Evaluate at c. Next, take the limit."},
                {"slide":6,"tts_text":"The rectangle has a finite area."}]
        plan=loop.plan_slide_repairs(
            slides,normalize,observations=[
                words("evaluate at circa next take the limit",h),
                words("the rectangle has a finite area",h)],
            wav_hashes=[h,h])
        calls=[]
        def mock_runner(spoken,folder,*,confirm_chargeable):
            calls.append((spoken,folder,confirm_chargeable))
            folder.mkdir()
            (folder/"diagnostic_cloud_tts_NOT_FORMAL.wav").write_bytes(b"test isolated")
            return {"publication_allowed":False,"wav_sha256":"c"*64}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            output=root/"run_diagnostic_auto"
            result=loop.run_isolated_diagnostic_repairs(
                plan,output,max_requests=1,cloud_runner=mock_runner)
            self.assertEqual(result["calls"],1)
            self.assertFalse(result["publication_allowed"])
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][0],"Evaluate at see. Next, take the limit.")
            self.assertTrue(calls[0][2])
            self.assertFalse((root/"slide5.wav").exists())
            self.assertFalse(result.get("phonetic_identity_verified"))
            with self.assertRaises(loop.PronunciationClosedLoopError):
                loop.run_isolated_diagnostic_repairs(
                    plan,output,max_requests=1,cloud_runner=mock_runner)

    def test_repair_is_not_triggered_on_unrelated_transcript_error(self):
        h="b"*64
        plan=loop.plan_slide_repairs(
            [{"slide":1,"tts_text":"The function is continuous."}],normalize,
            observations=[words("the fraction is continuous",h)],wav_hashes=[h])
        with tempfile.TemporaryDirectory() as temp:
            result=loop.run_isolated_diagnostic_repairs(
                plan,Path(temp)/"unused_diagnostic_folder",
                cloud_runner=lambda *a,**k: self.fail("No provider call authorized"))
            self.assertEqual(result["calls"],0)

    def test_repair_refuses_more_candidates_than_explicit_billing_budget(self):
        h="b"*64
        slides=[{"slide":i+1,"tts_text":"Evaluate at c. Next, take the limit."}
                for i in range(3)]
        plan=loop.plan_slide_repairs(slides,normalize,
            observations=[words("evaluate at circa next take the limit",h)]*3,
            wav_hashes=[h]*3)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"limited_diagnostic"
            with self.assertRaises(loop.PronunciationClosedLoopError):
                loop.run_isolated_diagnostic_repairs(
                    plan,dest,max_requests=2,
                    cloud_runner=lambda *a,**k: self.fail("Cannot charge"))
            self.assertFalse(dest.exists())

    def test_plan_immutable_and_no_production_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            user=root/"slide1.wav"
            user.write_bytes(b"protected")
            output=root/"new_plan.json"
            report=loop.plan_slide_repairs([{"slide":1,"tts_text":"Consider ln(x)."}],normalize)
            loop.write_immutable_plan(output,report)
            before=output.read_bytes()
            with self.assertRaises(loop.PronunciationClosedLoopError):
                loop.write_immutable_plan(output,report)
            self.assertEqual(output.read_bytes(),before)
            self.assertEqual(user.read_bytes(),b"protected")

if __name__ == "__main__":
    unittest.main()
