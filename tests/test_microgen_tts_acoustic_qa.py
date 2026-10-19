"""Adversarial offline audio-QA gate tests. No network, Whisper, or TTS calls."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_acoustic_qa as aq
import microgen_tts_provenance as p
from text_to_speech_v25 import normalize_scientific_speech as normalize


def make_wav(target: Path):
    with wave.open(str(target), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\0\0"*24000)


def build_verified(folder: Path, texts):
    records = []
    for i, raw in enumerate(texts,1):
        wav = folder/f"slide{i}.wav"
        make_wav(wav)
        records.append(p.make_record(
            slide=i,path=wav,text=normalize(raw),provider="google_cloud_chirp3",
            key=f"key{i}",voice_name="en-US-Chirp-HD-F",
            language_code="en-US",speaking_rate=0.8,location="global"))
    p.write_manifest(folder,records,list(map(normalize,texts)))


class AcousticQATests(unittest.TestCase):
    def test_identical_transcripts_still_require_listening(self):
        expected=["Because continuous graphs have no breaks, they possess a powerful global property described by the Intermediate Value Theorem."]
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td); build_verified(stage,expected)
            report=aq.audit_with_recognizer(stage, expected,lambda w:expected[0], normalize, independent_recognizer=lambda w:expected[0])
            self.assertEqual(report["review_required_slides"],[])
            self.assertEqual(report["slides"][0]["assessment"],"ASR_SCREEN_PASS_LISTENING_REQUIRED")
            self.assertFalse(report["publishable"])
            self.assertFalse(report["human_listening_approved"])

    def test_circa_instead_of_variable_c_flags_error(self):
        src=["The function is defined at c. Second, the limit exists."]
        heard="The function is defined at circa. Second, the limit exists."
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,src)
            report=aq.audit_with_recognizer(stage,src,lambda w:heard,normalize, independent_recognizer=lambda w:heard)
            row=report["slides"][0]
            self.assertEqual(report["review_required_slides"],[1])
            self.assertGreater(row["comparisons"][0]["circa_red_flags"],0)
            self.assertEqual(row["assessment"],"REVIEW_REQUIRED_PRONUNCIATION_RISK")

    def test_unclear_and_altered_math_word_flags(self):
        expectation="The Intermediate Value Theorem guarantees every intermediate value."
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,[expectation])
            report=aq.audit_with_recognizer(stage,[expectation],
                lambda _: "The intermediate valley theorem guarantees every intermediate value.",
                normalize, independent_recognizer=lambda _: "The intermediate valley theorem guarantees every intermediate value.")
            self.assertEqual(report["review_required_slides"],[1])
            self.assertGreater(report["slides"][0]["comparisons"][0]["sensitive_mismatches"],0)

    def test_two_audio_recognition_passes_must_agree(self):
        statement="When graphs are continuous the function traverses the closed interval."
        outputs=iter([
            statement,
            "When graphs are discontinuous the function traverses the closed interval."
        ])
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,[statement])
            report=aq.audit_with_recognizer(stage,[statement],
                lambda w:next(outputs),normalize, independent_recognizer=lambda w:next(outputs))
            self.assertEqual(report["slides"][0]["assessment"],
                             "REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE")

    def test_unclear_audio_marker_always_requires_review(self):
        expected="The Intermediate Value Theorem is true for a continuous function."
        heard="The Intermediate Value Theorem is true for a [unclear] function."
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,[expected])
            report=aq.audit_with_recognizer(
                stage,[expected],lambda w:heard,normalize,
                independent_recognizer=lambda w:heard)
            self.assertEqual(report["slides"][0]["assessment"],
                             "REVIEW_REQUIRED_UNCLEAR_SPEECH")

    def test_missing_second_independent_recognizer_never_passes(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,["The function is continuous."])
            with self.assertRaisesRegex(ValueError, "independent"):
                aq.audit_with_recognizer(
                    stage,["The function is continuous."],
                    lambda w:"The function is continuous.",normalize)

    def test_transcription_service_failure_does_not_pass(self):
        expected="The Intermediate Value Theorem is true."
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,[expected])
            attempts=[]
            def outage(w):
                attempts.append(1)
                raise RuntimeError("503 UNAVAILABLE")
            result=aq.audit_with_recognizer(stage,[expected],outage,normalize, independent_recognizer=outage)
            self.assertEqual(len(attempts),2)
            self.assertEqual(result["review_required_slides"],[1])
            self.assertEqual(result["slides"][0]["assessment"],
                             "REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE")

    def test_outage_is_bounded_across_many_slides(self):
        texts=["The function is continuous.", "The limit exists.", "Theorem follows."]
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,texts)
            calls=[]
            def unavailable(w):
                calls.append(w.name)
                raise RuntimeError("503 high demand")
            result=aq.audit_with_recognizer(
                stage,texts,unavailable,normalize,
                independent_recognizer=unavailable)
            self.assertEqual(len(calls),2)
            self.assertEqual(result["review_required_slides"],[1,2,3])
            self.assertEqual(result["unavailable_recognizer_passes"],[0,1])
            self.assertFalse(result["publishable"])

    def test_bad_wave_hash_blocks_before_any_recognition(self):
        expected="The function has a limit."
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,[expected])
            with (stage/"slide1.wav").open("ab") as f:
                f.write(b"unverified")
            invoked=[]
            with self.assertRaises(p.TTSProvenanceError):
                aq.audit_with_recognizer(stage,[expected],
                    lambda w:invoked.append(w) or expected,normalize, independent_recognizer=lambda w:expected)
            self.assertEqual(invoked,[])

    def test_unrecognized_word_and_missing_word_trigger_review(self):
        exp="A continuous function must take every intermediate value in between."
        heard="A continuous function must take every value in between."
        comparison=aq.mismatch_details(exp,heard)
        self.assertGreater(comparison["difference_fraction_upper_bound"],0.05)
        self.assertTrue(any(i["expected"]=="intermediate" for i in comparison["differences"]))

    def test_homophone_normalization_does_not_make_false_circa(self):
        comp=aq.mismatch_details("The value is see.", "The value is sea.")
        self.assertEqual(comp["circa_red_flags"],0)
        self.assertEqual(comp["difference_fraction_upper_bound"],0)

    def test_missing_or_corrupt_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);make_wav(stage/"slide1.wav")
            with self.assertRaises(p.TTSProvenanceError):
                aq.audit_with_recognizer(stage,["Any expected text."],
                    lambda w:"Any expected text.",normalize, independent_recognizer=lambda w:"Any expected text.")

    def test_no_silent_relaxation_of_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            stage=Path(td);build_verified(stage,["At c. Then go."])
            with self.assertRaises(ValueError):
                aq.audit_with_recognizer(stage,["At c. Then go."],
                    lambda w:"At see. Then go.",normalize,
                    independent_recognizer=lambda w:"At see. Then go.",
                    max_difference_fraction=0.8)
            with self.assertRaises(ValueError):
                aq.audit_with_recognizer(stage,["At c. Then go."],
                    lambda w:"At see. Then go.",normalize,
                    independent_recognizer=None)


if __name__=="__main__":
    unittest.main()
