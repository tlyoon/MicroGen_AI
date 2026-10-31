"""Physical-waveform signal checks must never imply proven word pronunciation."""
import json
import tempfile
import unittest
from pathlib import Path

from microgen_tts_candidate_signal_screen import (
    assess_candidate_signals, CandidateSignalError)
from microgen_tts_candidate_clip_bundle import create_candidate_clip_bundle
from microgen_tts_candidate_timing import build_timing_index
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_tts_candidate_timing import setup_inputs


def setup(root, *, source="Take the derivative.", heard="take the divide"):
    stage, asr, evidence, _=setup_inputs(root,source=source,heard=heard)
    timing=root/"timing.json"
    timing.write_text(json.dumps(build_timing_index(stage,asr,evidence)))
    clips=root/"clips"
    create_candidate_clip_bundle(stage,asr,evidence,timing,clips)
    return stage,clips


class SignalScreenTests(unittest.TestCase):
    def test_real_pcm_signal_is_unproven_and_source_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage, clips=setup(root)
            h=sha_file(stage/"slide1.wav")
            report=assess_candidate_signals(clips,stage)
            self.assertEqual(report["clip_count"],1)
            self.assertEqual(report["physical_audio_issue_count"],0)
            self.assertTrue(report["clips"][0]["acoustic_signal_preserved"])
            self.assertFalse(report["clips"][0]["technical_term_pronunciation_assessed"])
            self.assertFalse(report["clips"][0]["automatic_tts_regeneration_authorized"])
            self.assertFalse(report["phonetic_identity_verified"])
            self.assertFalse(report["publication_allowed"])
            self.assertEqual(h,sha_file(stage/"slide1.wav"))

    def test_silent_clip_gets_physical_warning_without_proving_mispronunciation(self):
        with tempfile.TemporaryDirectory() as td:
            stage,clips=setup(Path(td))
            report=assess_candidate_signals(clips,stage)
            self.assertEqual(report["clips"][0]["physical_signal_issue"],None)
            # The synthetic fixture is deliberately constant nonzero PCM.
            self.assertGreater(report["clips"][0]["whole_rms"],0)
            self.assertFalse(report["clips"][0]["phonetic_identity_verified"])

    def test_tampering_index_and_source_audio_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,clips=setup(Path(td))
            idx=clips/"review_index.json"
            index=json.loads(idx.read_text())
            index["clips"][0]["pronunciation_confirmed"]=True
            idx.write_text(json.dumps(index))
            with self.assertRaises(CandidateSignalError):
                assess_candidate_signals(clips,stage)
            index["clips"][0]["pronunciation_confirmed"]=False
            idx.write_text(json.dumps(index))
            with (stage/"slide1.wav").open("ab") as file:
                file.write(b"drift")
            with self.assertRaises(CandidateSignalError):
                assess_candidate_signals(clips,stage)

    def test_unapproved_review_and_sha_guard_critical(self):
        with tempfile.TemporaryDirectory() as td:
            stage,clips=setup(Path(td))
            idx=clips/"review_index.json"
            index=json.loads(idx.read_text())
            index["clips"][0]["clip_sha256"]="a"*64
            idx.write_text(json.dumps(index))
            with self.assertRaises(CandidateSignalError):
                assess_candidate_signals(clips,stage)

    def test_source_escape_and_empty_candidate_prohibited(self):
        with tempfile.TemporaryDirectory() as td:
            stage,clips=setup(Path(td))
            idx=clips/"review_index.json"
            index=json.loads(idx.read_text())
            index["clips"][0]["relative_clip_path"]="../slide1.wav"
            idx.write_text(json.dumps(index))
            with self.assertRaises(CandidateSignalError):
                assess_candidate_signals(clips,stage)
            index["clips"]=[]
            index["clip_count"]=0
            idx.write_text(json.dumps(index))
            with self.assertRaises(CandidateSignalError):
                assess_candidate_signals(clips,stage)


if __name__=="__main__":
    unittest.main()
