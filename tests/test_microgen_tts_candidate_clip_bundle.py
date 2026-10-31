"""No-provider regression for SHA-bound, external candidate listening excerpts."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

from microgen_pronunciation_closed_loop import sha_file
from microgen_tts_candidate_timing import build_timing_index
from microgen_tts_candidate_clip_bundle import (
    CandidateClipBundleError, create_candidate_clip_bundle)
from test_microgen_tts_candidate_timing import setup_inputs


def case(root, **kwargs):
    stage, asr, evidence, report = setup_inputs(root, **kwargs)
    timing = root / "timing.json"
    timing.write_text(json.dumps(build_timing_index(stage, asr, evidence)),
                      encoding="utf-8")
    return stage, asr, evidence, timing, report


class ClipBundleTests(unittest.TestCase):
    def test_pcm_exact_real_audio_and_closed_review_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, timing, report = case(root)
            sources = [stage / "slide1.wav", report, evidence, timing]
            original = [sha_file(p) for p in sources]
            output = root / "external_clips"
            result = create_candidate_clip_bundle(
                stage, asr, evidence, timing, output)
            self.assertEqual(result["clip_count"], 1)
            self.assertEqual(result["skipped_count"], 0)
            entry = result["clips"][0]
            clip = output / entry["relative_clip_path"]
            self.assertTrue(clip.is_file())
            self.assertEqual(sha_file(clip), entry["clip_sha256"])
            self.assertEqual(entry["expected"], "derivative")
            self.assertEqual(entry["recognized"], "divide")
            self.assertFalse(entry["pronunciation_confirmed"])
            self.assertFalse(entry["automatic_repair_allowed"])
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["phonetic_identity_verified"])
            self.assertEqual([sha_file(p) for p in sources], original)
            with wave.open(str(stage / "slide1.wav"), "rb") as src, wave.open(
                    str(clip), "rb") as snippet:
                a = round(entry["start_seconds"] * src.getframerate())
                src.setpos(a)
                self.assertEqual(src.readframes(snippet.getnframes()),
                                 snippet.readframes(snippet.getnframes()))
            self.assertEqual(json.loads((output / "review_index.json").read_text()),
                             result)
            with self.assertRaises(CandidateClipBundleError):
                create_candidate_clip_bundle(stage, asr, evidence, timing, output)

    def test_reject_tampered_timing_without_writing_any_clip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, timing, _ = case(root)
            fake = json.loads(timing.read_text())
            fake["candidates"][0]["asr_matched_span"]["start_seconds"] = 0.9
            timing.write_text(json.dumps(fake))
            with self.assertRaises(CandidateClipBundleError):
                create_candidate_clip_bundle(
                    stage, asr, evidence, timing, root / "clips")
            self.assertFalse((root / "clips").exists())

    def test_ambiguous_asr_span_skipped_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, timing, _ = case(
                root, source="Take the derivative then divide.",
                heard="take the divide then divide")
            result = create_candidate_clip_bundle(
                stage, asr, evidence, timing, root / "clips")
            self.assertEqual(result["clip_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"],
                             "NONUNIQUE_OR_MISSING_ASR_TIMING")

    def test_budgets_and_original_drive_protection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, timing, _ = case(root)
            cases = [
                {"max_candidates": 0},
                {"padding_seconds": 2.5},
                {"max_total_seconds": .1}
            ]
            for n, opts in enumerate(cases):
                dest = root / f"no_output_{n}"
                with self.subTest(opts=opts), self.assertRaises(
                        CandidateClipBundleError):
                    create_candidate_clip_bundle(
                        stage, asr, evidence, timing, dest, **opts)
                self.assertFalse(dest.exists())
            with self.assertRaises(CandidateClipBundleError):
                create_candidate_clip_bundle(
                    stage, asr, evidence, timing, stage / "inside_source")
            drive = root / "My Drive"
            drive.mkdir()
            with self.assertRaises(CandidateClipBundleError):
                create_candidate_clip_bundle(
                    stage, asr, evidence, timing, drive / "bad")

    def test_original_wav_drift_invalidates_clip_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage, asr, evidence, timing, _ = case(root)
            with (stage / "slide1.wav").open("ab") as stream:
                stream.write(b"modified")
            with self.assertRaises(Exception):
                create_candidate_clip_bundle(
                    stage, asr, evidence, timing, root / "clips")
            self.assertFalse((root / "clips").exists())


if __name__ == "__main__":
    unittest.main()
