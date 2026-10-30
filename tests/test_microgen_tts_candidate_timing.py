"""Real PCM-backed targeted technical-word timing is ASR evidence, never approval."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_candidate_timing as timing
from microgen_pronunciation_closed_loop import sha_file
from microgen_pronunciation_evidence_pipeline import build_post_tts_evidence
from text_to_speech_v25 import normalize_scientific_speech


def setup_inputs(root, *, source="Take the derivative.", heard="take the divide"):
    stage, asr_dir = root / "stage", root / "asr"
    stage.mkdir()
    asr_dir.mkdir()
    slides = [{"slide": 1, "tts_text": source}]
    (stage / "script_tts.json").write_text(json.dumps({"slides": slides}), encoding="utf8")
    (stage / ".microgen_tts_provenance.json").write_text('{"schema_version":1}')
    wav_path = stage / "slide1.wav"
    with wave.open(str(wav_path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\x00\x01" * 32000)
    audio_sha = sha_file(wav_path)
    words = [{"word": token, "start": i * .1, "end": (i + 1) * .1,
              "conf": .85} for i, token in enumerate(heard.split())]
    observation = {"source_wav_sha256": audio_sha, "words": words,
                   "phonetic_identity_verified": False,
                   "semantic_word_alignment_certified": False}
    report = {"slide": 1, "wav_sha256": audio_sha, "recognition": observation}
    asr_path = asr_dir / "slide01.json"
    asr_path.write_text(json.dumps(report), encoding="utf8")
    evidence = build_post_tts_evidence(stage, slides, normalize_scientific_speech,
                                       observations=[observation])
    evidence_path = root / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf8")
    return stage, asr_dir, evidence_path, asr_path


class CandidateTimingTests(unittest.TestCase):
    def test_unique_word_timing_preserves_pcm_and_no_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, _ = setup_inputs(root)
            before = sha_file(stage / "slide1.wav")
            result = timing.build_timing_index(stage, asr, evidence)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["unambiguous_asr_spans"], 1)
            item = result["candidates"][0]
            self.assertEqual((item["expected"], item["recognized"]),
                             ("derivative", "divide"))
            self.assertEqual(item["status"], "UNIQUE_ASR_SPAN_UNVERIFIED")
            self.assertAlmostEqual(item["asr_matched_span"]["start_seconds"], .2)
            self.assertEqual(item["original_wav_sha256"], before)
            self.assertEqual(sha_file(stage / "slide1.wav"), before)
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["phonetic_identity_verified"])
            self.assertFalse(item["pronunciation_confirmed"])

    def test_ambiguous_recognizer_span_does_not_guess_a_time(self):
        with tempfile.TemporaryDirectory() as td:
            stage, asr, evidence, _ = setup_inputs(
                Path(td), source="Take the derivative then divide.",
                heard="take the divide then divide")
            result = timing.build_timing_index(stage, asr, evidence)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["unambiguous_asr_spans"], 0)
            self.assertEqual(result["candidates"][0]["status"],
                             "AMBIGUOUS_ASR_SPAN")
            self.assertIsNone(result["candidates"][0]["asr_matched_span"])

    def test_wav_hash_and_timestamp_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage, asr, evidence, path = setup_inputs(Path(td))
            data = json.loads(path.read_text())
            data["wav_sha256"] = "a" * 64
            path.write_text(json.dumps(data))
            with self.assertRaises(timing.CandidateTimingError):
                timing.build_timing_index(stage, asr, evidence)
            data["wav_sha256"] = sha_file(stage / "slide1.wav")
            data["recognition"]["words"][1]["end"] = 8.0
            path.write_text(json.dumps(data))
            with self.assertRaises(timing.CandidateTimingError):
                timing.build_timing_index(stage, asr, evidence)

    def test_forged_pronunciation_receipt_and_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, _ = setup_inputs(root)
            original = json.loads(evidence.read_text())
            original["phonetic_identity_verified"] = True
            evidence.write_text(json.dumps(original))
            with self.assertRaises(timing.CandidateTimingError):
                timing.build_timing_index(stage, asr, evidence)
            original["phonetic_identity_verified"] = False
            evidence.write_text(json.dumps(original))
            output = root / "already.json"
            output.write_text("protected")
            with self.assertRaises(timing.CandidateTimingError):
                timing.main(["--stage", str(stage), "--asr-dir", str(asr),
                             "--evidence", str(evidence),
                             "--new-output", str(output)])
            self.assertEqual(output.read_text(), "protected")


if __name__ == "__main__":
    unittest.main()
