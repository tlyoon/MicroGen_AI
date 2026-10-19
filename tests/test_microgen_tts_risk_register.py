"""Regression for pronunciation risks ASR can silently autocorrect."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_risk_register as risk
import microgen_tts_acoustic_qa as acoustic
import microgen_tts_provenance as provenance
from text_to_speech_v25 import normalize_scientific_speech as normalize


def wav(path):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\0\0"*24000)


def provenanced(folder, originals):
    rec=[]
    for i,text in enumerate(originals,1):
        path=folder/f"slide{i}.wav"
        wav(path)
        rec.append(provenance.make_record(
            slide=i,path=path,text=normalize(text),
            provider="google_cloud_chirp3",key=f"test-cache-{i}",
            voice_name="en-US-Chirp-HD-F",language_code="en-US",
            speaking_rate=0.8,location="global",
        ))
    provenance.write_manifest(folder,rec,[normalize(x) for x in originals])


class RiskTests(unittest.TestCase):
    def test_confirmed_yay_defect_is_risk_even_when_normalized(self):
        source="The Intermediate Value Theorem passes every y-value between the end y-values."
        spoken=normalize(source)
        self.assertEqual(spoken.count("why value"),2)
        result=risk.find_pronunciation_risks(source,spoken)
        self.assertEqual([x.code for x in result],
                         ["math_letter_compound","math_letter_compound"])
        self.assertTrue(all(x.automatic_text_correction for x in result))
        self.assertTrue(all(x.expected_spoken.startswith("why value") for x in result))

    def test_previously_confirmed_circa_detected_and_safe(self):
        sentence="A function is defined at c. Second, it approaches c. Then compare."
        got=risk.find_pronunciation_risks(sentence,normalize(sentence))
        self.assertEqual([r.code for r in got],
                         ["math_c_sentence","math_c_sentence"])
        self.assertTrue(all(x.expected_spoken=="see." for x in got))

    def test_ambiguous_script_requires_reviewer_instead_of_guessing(self):
        raw="Take f(x), compute x_1, then evaluate sin x and α."
        found=risk.find_pronunciation_risks(raw,normalize(raw))
        categories={r.code for r in found}
        self.assertTrue({"function_argument","subscript","math_abbreviation",
                         "greek_symbol"}.issubset(categories))
        self.assertTrue(any(not x.automatic_text_correction for x in found))

    def test_normal_words_and_historical_circa_not_risky(self):
        for phrase in ("A letter arrived c. 1900.",
                       "Yesterday was sunny.",
                       "Yale is a university.",
                       "He asked why it rains.",
                       "The Y-shaped garden is beautiful."):
            with self.subTest(phrase=phrase):
                self.assertFalse(risk.find_pronunciation_risks(phrase,normalize(phrase)))

    def test_standalone_mathematical_variable_is_flagged_not_changed(self):
        raw="The variable y approaches zero."
        found=risk.find_pronunciation_risks(raw,normalize(raw))
        self.assertEqual([x.code for x in found],["standalone_math_letter"])
        self.assertFalse(found[0].automatic_text_correction)

    def test_passing_two_asr_transcripts_cannot_clear_letter_risk(self):
        src=["The continuous function takes every y-value."]
        spoken=normalize(src[0])
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);provenanced(stage,src)
            result=acoustic.audit_with_recognizer(
                stage,src,lambda _:spoken,normalize,
                independent_recognizer=lambda _:spoken)
            self.assertEqual(result["risk_review_slides"],[1])
            self.assertEqual(result["review_required_slides"],[1])
            self.assertEqual(result["slides"][0]["assessment"],
                             "REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK")
            self.assertFalse(result["publishable"])
            self.assertEqual(len(result["slides"][0]["source_pronunciation_risks"]),1)

    def test_audio_outage_and_source_risk_still_block(self):
        src=["The function has a y-coordinate."]
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);provenanced(stage,src)
            def fail(_):raise RuntimeError("503 outage")
            result=acoustic.audit_with_recognizer(
                stage,src,fail,normalize,independent_recognizer=fail)
            self.assertEqual(result["risk_review_slides"],[1])
            self.assertEqual(result["slides"][0]["assessment"],
                             "REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE")

    def test_realistic_review_plan_measured_slide_bounds(self):
        slides=[
           {"slide":1,"tts_text":"Introductory lecture."},
           {"slide":2,"tts_text":"A graph passes through a y-value and at c. Next."},
        ]
        report=risk.build_risk_register(slides,normalize,[3.125,28.0])
        self.assertEqual(report["slide_count"],2)
        self.assertEqual(report["risk_review_slides"],[2])
        self.assertEqual(report["slides"][1]["slide_start_seconds"],3.125)
        self.assertEqual(report["slides"][1]["slide_end_seconds"],31.125)
        self.assertGreaterEqual(report["risk_count"],2)
        self.assertFalse(report["publishable"])

    def test_refuses_bad_slide_sequence_and_timing_and_asr_mapping(self):
        with self.assertRaises(ValueError):
            risk.build_risk_register([{"slide":4,"tts_text":"no"}],normalize)
        with self.assertRaises(ValueError):
            risk.build_risk_register([{"slide":1,"tts_text":"hello"}],normalize,[-1])
        with self.assertRaises(ValueError):
            risk.build_risk_register([{"slide":1,"tts_text":"hello"}],normalize,
                                     acoustic_report={"slide_count":1,"slides":[{"slide":2}]})

    def test_time_codes_are_slide_bounds_not_claimed_word_timestamps(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            wav(p/"slide1.wav")
            self.assertEqual(risk.durations_from_wavs(p,1),[1.0])

    def test_immutable_risk_report_binds_to_wav_checksum(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td)
            source=[{"slide":1,"tts_text":"The y-value varies."}]
            sha1="1"*64;sha2="2"*64
            one=risk.build_risk_register(source,normalize,[1.0],wav_sha256=[sha1])
            path1=risk.save_immutable_risk_report(stage,one)
            self.assertEqual(risk.save_immutable_risk_report(stage,one),path1)
            two=risk.build_risk_register(source,normalize,[1.0],wav_sha256=[sha2])
            path2=risk.save_immutable_risk_report(stage,two)
            self.assertNotEqual(path1,path2)
            self.assertEqual(json.loads(path1.read_text())["slides"][0]["audio_wav_sha256"],sha1)
            original=path1.read_bytes()
            path1.write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                risk.save_immutable_risk_report(stage,one)
            self.assertNotEqual(path1.read_bytes(),original)

    def test_repair_plan_only_for_reviewed_automatic_rule(self):
        source=[
            {"slide":1,"tts_text":"The y-value is continuous at c. Next."},
            {"slide":2,"tts_text":"Study f(x) and its graph."},
        ]
        report=risk.build_risk_register(source,normalize)
        self.assertEqual(report["suggested_isolated_repair_slides"],[1])
        self.assertEqual(report["risk_review_slides"],[1,2])
        self.assertTrue(all(not a["publishable"] for s in report["slides"]
                            for a in s["repair_actions"]))
        self.assertEqual(
            report["slides"][1]["repair_actions"][0]["action"],
            "REVIEW_AND_AUTHOR_EXPLICIT_TTS_ONLY_TEXT_BEFORE_SYNTHESIS"
        )

    def test_rejects_partial_or_unreadable_audio_hash_inventory(self):
        src=[{"slide":1,"tts_text":"The y-value is continuous."}]
        with self.assertRaises(ValueError):
            risk.build_risk_register(src,normalize,wav_sha256=[])
        with self.assertRaises(ValueError):
            risk.build_risk_register(src,normalize,wav_sha256=["corrupt"])

    def test_nonoverwriting_json_report_guard(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            src=p/"script_tts.json"
            src.write_text(json.dumps({"slides":[{"slide":1,"tts_text":"y-value"}]}),
                           encoding="utf8")
            out=p/"risk_report.json"
            self.assertEqual(risk.main([str(src),"--report",str(out)]),0)
            before=out.read_bytes()
            with self.assertRaises(SystemExit):
                risk.main([str(src),"--report",str(out)])
            self.assertEqual(out.read_bytes(),before)


if __name__=="__main__":
    unittest.main()
