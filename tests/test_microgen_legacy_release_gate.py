"""No release action or approval is inferred from valid video-only candidates."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_release_gate as gate


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "1.2"
        self.source.mkdir()
        self.pdf = self.root / "corrected.pdf"
        self.pdf.write_bytes(b"candidate")
        self.video = self.root / "video"
        self.video.mkdir()
        self.sha = gate.quality.sha256(self.pdf)

    def passed_record(self):
        return {
            "corrected_mp4_sha256": "f" * 64,
            "visual_scene_validation": [{}, {}, {}],
            "candidate_video_verification": {
                "corrected_scene_validation": [
                    {"expected_mean_absolute_pixel_difference": 3.5},
                    {"expected_mean_absolute_pixel_difference": 4.1},
                    {"expected_mean_absolute_pixel_difference": 2.9}],
                "scene_timing_error_seconds": [0.0, 0.2]
            }
        }

    def run_inspection(self, section="1.2", record=None, provenance=None):
        record = record or self.passed_record()
        if provenance is None:
            provenance = {"narration_sidecar_sha256": "1" * 64, "wav_files_present": 0}
        with mock.patch.object(gate.quality, "check_slide_pdf", return_value={"pages": 3}), \
             mock.patch.object(gate, "validate_completed", return_value=record), \
             mock.patch.object(gate, "inspect_source_timing_provenance", return_value=provenance):
            return gate.inspect_release(self.source, self.pdf, self.video,
                                        expected_pdf_sha256=self.sha, section=section)

    def test_passing_video_is_not_publication_authorization(self):
        out = self.run_inspection()
        self.assertEqual(out["status"], "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW")
        self.assertFalse(out["may_publish"])
        self.assertFalse(out["completion_receipt_created"])
        self.assertFalse(out["academic_review_signed_by_tool"])
        self.assertTrue(any("WAV" in a for a in out["advisories"]))

    def test_missing_narration_sidecar_blocks_release(self):
        out = self.run_inspection(provenance={"wav_files_present": 0})
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("sidecar" in text for text in out["reasons"]))

    def test_scene_count_or_timing_mismatch_blocks(self):
        record = self.passed_record()
        record["candidate_video_verification"]["scene_timing_error_seconds"] = [0.8, 0.0]
        out = self.run_inspection(record=record)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("timing" in r for r in out["reasons"]))
        record["candidate_video_verification"]["scene_timing_error_seconds"] = [0.0]
        self.assertEqual(self.run_inspection(record=record)["status"], "BLOCKED")

    def test_known_spoken_title_defects_block_even_with_good_video(self):
        with mock.patch.object(gate.quality, "check_slide_pdf", return_value={"pages": 3}), \
             mock.patch.object(gate, "validate_completed", return_value=self.passed_record()), \
             mock.patch.object(gate, "inspect_source_timing_provenance",
                               return_value={"narration_sidecar_sha256": "1" * 64, "wav_files_present": 3}):
            folder = self.root / "7.2"
            folder.mkdir()
            result = gate.inspect_release(folder, self.pdf, self.video,
                                          expected_pdf_sha256=self.sha, section="7.2")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("truncated" in r for r in result["reasons"]))

    def test_corrupted_pdf_or_wrong_section_fails_closed(self):
        self.assertEqual(self.run_inspection("5.9")["status"], "BLOCKED")
        out = gate.inspect_release(self.source, self.pdf, self.video,
                                   expected_pdf_sha256="0" * 64, section="1.2")
        self.assertTrue(any("SHA256" in x for x in out["reasons"]))

    def test_failed_video_hash_prevents_release(self):
        with mock.patch.object(gate.quality, "check_slide_pdf", return_value={"pages": 3}), \
             mock.patch.object(gate, "validate_completed", side_effect=gate.BatchError("tampered")):
            out = gate.inspect_release(self.source, self.pdf, self.video,
                                       expected_pdf_sha256=self.sha, section="1.2")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("tampered" in x for x in out["reasons"]))


if __name__ == "__main__":
    unittest.main()
