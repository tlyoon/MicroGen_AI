"""Strict split-verification normalization without rewriting historic media."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_split_evidence as e


class SplitProofTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.source = self.root / "course" / "1.2"
        self.source.mkdir(parents=True)
        self.old = self.root / "private_archive"
        self.old.mkdir()
        self.output = self.root / "prepared"
        for directory in (self.old, self.source):
            (directory / "slides.pdf").write_bytes(b"source-pdf")
            (directory / "slides.mp4").write_bytes(b"source-mp4")
        (self.old / "corrected_slides.pdf").write_bytes(b"corrected-pdf")
        (self.old / "corrected_slides.mp4").write_bytes(b"corrected-mp4")
        self.source_pdf_hash = e.sha256(self.source / "slides.pdf")
        self.source_video_hash = e.sha256(self.source / "slides.mp4")
        self.corrected_pdf_hash = e.sha256(self.old / "corrected_slides.pdf")
        self.corrected_video_hash = e.sha256(self.old / "corrected_slides.mp4")
        scenes = [
            {"scene": 1, "matching_pdf_page": 1,
             "expected_mean_absolute_pixel_difference": 3.0},
            {"scene": 2, "matching_pdf_page": 2,
             "expected_mean_absolute_pixel_difference": 2.0},
        ]
        self.report = {
            "status": "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED",
            "old_media_sha256": {
                "old_pdf": self.source_pdf_hash,
                "old_mp4": self.source_video_hash,
                "corrected_pdf": self.corrected_pdf_hash,
            },
            "corrected_mp4_sha256": self.corrected_video_hash,
            "original_audio_sha256": "a"*64,
            "candidate_audio_sha256": "a"*64,
            "visual_scene_validation": scenes,
            "video_slide_boundaries_seconds": [5.0],
            "candidate_seconds": 40.0,
        }
        self.proof = {
            "status": "VERIFIED_ISOLATED_CANDIDATE_NOT_PUBLISHED",
            "candidate_mp4_sha256": self.corrected_video_hash,
            "source_pdf_sha256": self.corrected_pdf_hash,
            "original_audio_sha256": "a"*64,
            "candidate_audio_sha256": "a"*64,
            "same_audio_packets": True,
            "corrected_scene_validation": scenes,
            "scene_timing_error_seconds": [0.0],
            "candidate_boundaries_seconds": [5.0],
            "corrected_video_seconds": 40.0,
        }
        self.write()

    def write(self):
        (self.old / "video_repair_report.json").write_text(json.dumps(self.report))
        (self.old / "independent_postrender_verification.json").write_text(json.dumps(self.proof))

    def normalize(self):
        with mock.patch.object(e, "audio_stream_hash", return_value="a"*64), \
             mock.patch.object(e, "check_slide_pdf", return_value={"pages": 2}), \
             mock.patch.object(e, "validate_completed", return_value={}), \
             mock.patch.object(e, "inspect_release", return_value={
                 "status": "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW",
                 "reasons": []}):
            return e.normalize(self.source, self.old, self.output)

    def test_adapt_success_preserves_original_report_and_media(self):
        original = (self.old / "video_repair_report.json").read_bytes()
        old_video = (self.old / "corrected_slides.mp4").read_bytes()
        result = self.normalize()
        self.assertEqual(result["status"], "ADAPTED_CANDIDATE_PASSED_RELEASE_GATE_NOT_PUBLISHED")
        self.assertFalse(result["moodle_published"])
        self.assertFalse(result["candidate_media_reencoded"])
        self.assertEqual((self.old / "video_repair_report.json").read_bytes(), original)
        self.assertEqual((self.old / "corrected_slides.mp4").read_bytes(), old_video)
        self.assertEqual((self.output / "corrected_slides.mp4").read_bytes(), old_video)
        adapted = json.loads((self.output / "video_repair_report.json").read_text())
        self.assertEqual(len(adapted["candidate_video_verification"]["corrected_scene_validation"]), 2)
        self.assertFalse(adapted["historical_split_evidence_provenance"]["production_published"])

    def test_fail_if_source_was_changed(self):
        (self.source / "slides.pdf").write_bytes(b"drift")
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "Original source"):
            self.normalize()
        self.assertFalse(self.output.exists())

    def test_fail_on_independent_proof_pixel_defect(self):
        self.proof["corrected_scene_validation"][1]["expected_mean_absolute_pixel_difference"] = 20.0
        self.write()
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "pixel proof invalid"):
            self.normalize()
        self.assertFalse(self.output.exists())

    def test_fail_on_stale_media_hash(self):
        self.proof["candidate_mp4_sha256"] = "f" * 64
        self.write()
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "not identical"):
            self.normalize()

    def test_fail_on_audio_packet_discrepancy(self):
        self.proof["same_audio_packets"] = False
        self.write()
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "encoded audio"):
            self.normalize()

    def test_fail_on_scene_count_or_transition_drift(self):
        self.proof["scene_timing_error_seconds"] = [0.8]
        self.write()
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "transition drift"):
            self.normalize()

    def test_never_overwrite_existing_destination(self):
        self.output.mkdir()
        (self.output / "sentinel.txt").write_text("safe")
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "already exists"):
            self.normalize()
        self.assertEqual((self.output / "sentinel.txt").read_text(), "safe")

    def test_blocks_output_inside_source(self):
        with self.assertRaisesRegex(e.EvidenceAdaptationError, "overlaps"):
            with mock.patch.object(e, "audio_stream_hash", return_value="a"*64):
                e.normalize(self.source, self.old, self.source / "bad")

    def test_gate_failure_preserves_failed_candidate_for_review(self):
        with mock.patch.object(e, "audio_stream_hash", return_value="a"*64), \
             mock.patch.object(e, "check_slide_pdf", return_value={"pages": 2}), \
             mock.patch.object(e, "validate_completed", return_value={}), \
             mock.patch.object(e, "inspect_release", return_value={
                 "status": "BLOCKED", "reasons": ["incorrect"]}):
            with self.assertRaisesRegex(e.EvidenceAdaptationError, "Modern release gate"):
                e.normalize(self.source, self.old, self.output)
        self.assertTrue((self.output / "FAILED_ADAPTATION_DO_NOT_PROMOTE.txt").exists())


if __name__ == "__main__":
    unittest.main()
