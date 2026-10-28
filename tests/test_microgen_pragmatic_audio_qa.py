"""Regression: minor TTS uncertainty never causes blind retry loops."""
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from microgen_pragmatic_audio_qa import decide_media_progression, assess_pragmatic_audio_qa
from microgen_tts_provenance import make_record, write_manifest
from text_to_speech_v25 import normalize_scientific_speech as normalize


def fixture(folder, text="At c. Now inspect the value of x."):
    (folder/"script_tts.json").write_text(json.dumps({"slides":[{"slide":1,"tts_text":text}]}),encoding="utf8")
    f=folder/"slide1.wav"
    with wave.open(str(f),"wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b"\x10\x05"*24000)
    spoken=normalize(text)
    record=make_record(slide=1,path=f,text=spoken,provider="google_cloud_chirp3",
        key="fixture",voice_name="en-US-Chirp-HD-F",language_code="en-US",
        speaking_rate=.8,location="global")
    write_manifest(folder,[record],[spoken])
    return f


class PragmaticContractTests(unittest.TestCase):
    def decision(self,**changes):
        values={"preflight":True,"lexicon":True,"provenance":True,
                "pcm":True,"acoustic_report":None}
        values.update(changes)
        return decide_media_progression(**values)

    def test_absent_model_is_advisory_and_not_publication(self):
        report=self.decision()
        self.assertTrue(report["can_continue_media_generation"])
        self.assertIn("OPTIONAL_ASR_EVIDENCE_NOT_PRESENT",report["nonblocking_audio_advisories"])
        self.assertFalse(report["publication_allowed"])
        self.assertFalse(report["independent_phonetic_acceptance"])

    def test_math_letter_source_risk_unchanged_is_not_automatic_block(self):
        r={"slides":[{"assessment":"REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK",
                       "comparisons":[{"circa_red_flags":0,"letter_y_yay_red_flags":0}]}]}
        result=self.decision(acoustic_report=r)
        self.assertTrue(result["can_continue_media_generation"])
        self.assertEqual(result["workflow_state"],"CONTINUE_WITH_ADVISORIES")

    def test_circa_or_yay_negative_evidence_remains_critical(self):
        for key in ("circa_red_flags","letter_y_yay_red_flags"):
            with self.subTest(key=key):
                r={"slides":[{"assessment":"REVIEW_REQUIRED_PRONUNCIATION_RISK",
                    "comparisons":[{key:1}]}]}
                state=self.decision(acoustic_report=r)
                self.assertFalse(state["can_continue_media_generation"])
                self.assertTrue(any("RED_FLAG" in x for x in state["critical_audio_defects"]))

    def test_invalid_pcm_and_voice_always_block(self):
        for key in ("pcm","provenance","lexicon","preflight"):
            with self.subTest(key=key):
                self.assertFalse(self.decision(**{key:False})["can_continue_media_generation"])

    def test_model_disagreement_on_math_blocks_but_unavailable_warns(self):
        r={"slides":[{"assessment":"REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE",
                       "comparisons":[]}]}
        self.assertFalse(self.decision(acoustic_report=r)["can_continue_media_generation"])
        r["slides"][0]["assessment"]="REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE"
        self.assertTrue(self.decision(acoustic_report=r)["can_continue_media_generation"])

    def test_missing_provenance_not_hidden_by_good_wav(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);fixture(p)
            (p/".microgen_tts_provenance.json").unlink()
            result=assess_pragmatic_audio_qa(p)
            self.assertFalse(result["can_continue_media_generation"])

    def test_realistic_math_c_input_can_continue_but_no_audio_approval(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);fixture(p)
            result=assess_pragmatic_audio_qa(p)
            self.assertTrue(result["can_continue_media_generation"])
            self.assertGreater(result["source_risk_flags"],0)
            self.assertFalse(result["pronunciation_accepted"])
            self.assertFalse(result["publication_allowed"])


if __name__=="__main__":
    unittest.main()
