"""Fail-closed tests for distinct WAV-free legacy visual receipts and rollback."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_promotion as p


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.course = self.root / "course" / "2" / "2.2"
        self.course.mkdir(parents=True)
        for filename in p.REQUIRED:
            (self.course / filename).write_bytes(("original-" + filename).encode())
        (self.course / "moodle_lecture.xml").write_bytes(b"untouched")
        (self.course / "Figure 2.2.png").write_bytes(b"original figure")
        self.source_hashes = p.inventory(self.course)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        (self.candidate / "corrected_slides.pdf").write_bytes(b"corrected-pdf")
        (self.candidate / "corrected_slides.mp4").write_bytes(b"corrected-mp4")
        self.report = {
            "status": "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED",
            "corrected_mp4_sha256": p.quality.sha256(
                self.candidate / "corrected_slides.mp4"),
            "original_audio_sha256": "d" * 64,
            "candidate_audio_sha256": "d" * 64,
            "candidate_video_verification": {
                "corrected_scene_validation": [
                    {"scene": 1, "expected_mean_absolute_pixel_difference": 3.0},
                    {"scene": 2, "expected_mean_absolute_pixel_difference": 3.0}],
                "scene_timing_error_seconds": [0.0]
            },
            "old_media_sha256": {
                "old_mp4": p.quality.sha256(self.course / "slides.mp4"),
                "old_pdf": p.quality.sha256(self.course / "slides.pdf")
            },
        }
        (self.candidate / "video_repair_report.json").write_text(
            json.dumps(self.report), encoding="utf-8"
        )
        self.package = self.root / "review_package"
        self.pdf_sha = p.quality.sha256(self.candidate / "corrected_slides.pdf")

    def prepare(self):
        with mock.patch.object(p, "inspect_release", return_value={
            "status": "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW",
            "reasons": []
        }), mock.patch.object(p.quality, "check_graphics", return_value=[]):
            return p.prepare(
                self.course, self.candidate, self.package,
                section="2.2", expected_pdf_sha=self.pdf_sha)

    def second_backup(self):
        second = self.root / "independent_backup"
        p.snapshot(self.course, second / "original", self.source_hashes)
        return second

    def test_staged_bundle_backs_up_all_files_without_touching_course(self):
        result = self.prepare()
        self.assertEqual(result["state"], "PREPARED_NOT_PUBLISHED")
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(p.inventory(self.course), self.source_hashes)
        p.verify_package(self.package, self.course)
        self.assertEqual(p.quality.sha256(
            self.package / "candidate" / "slides.pdf"), self.pdf_sha)
        self.assertEqual(p.quality.sha256(self.package / "candidate" / p.EVIDENCE),
                         result["candidate_evidence_sha256"])
        receipt = json.loads((self.package / "candidate" / p.MARKER).read_text())
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["kind"], "legacy_visual_audio_preservation_v2")
        self.assertEqual(receipt["wav_status"], "not_retained_not_regenerated")
        self.assertFalse(receipt["human_signed_review_created"])
        self.assertEqual(p.quality.sha256(
            self.package / "original" / "moodle_lecture.xml"),
            self.source_hashes["moodle_lecture.xml"])

    def test_explicit_authorization_and_second_backup_required(self):
        self.prepare()
        with self.assertRaisesRegex(p.PromotionError, "authorization"):
            p.promote(self.course, self.package, self.root / "none",
                      section="2.2", assignment=Path("assignment.json"),
                      assignment_sha="a" * 64, campaign_id="trial",
                      code_sha="b" * 40, authorization="")
        with mock.patch.object(p, "verify_code"), \
             mock.patch.object(p, "DriveAssignedOwner") as owner:
            owner.return_value = mock.Mock(spec=["assert_held"])
            with self.assertRaisesRegex((p.PromotionError, OSError), "Backup|backup|original"):
                p.promote(self.course, self.package, self.root / "none",
                          section="2.2", assignment=Path("assignment.json"),
                          assignment_sha="a" * 64, campaign_id="trial",
                          code_sha="b" * 40,
                          authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
        self.assertEqual(p.inventory(self.course), self.source_hashes)

    def test_stale_candidate_or_course_drift_blocks(self):
        self.prepare()
        (self.course / "script_tts.json").write_bytes(b"tampered")
        with self.assertRaisesRegex(p.PromotionError, "changed after backup"):
            p.verify_package(self.package, self.course)
        (self.course / "script_tts.json").write_bytes(
            b"original-script_tts.json")
        (self.package / "candidate" / "slides.pdf").write_bytes(b"drift")
        with self.assertRaisesRegex(p.PromotionError, "changed"):
            p.verify_package(self.package, self.course)

    def test_existing_receipts_are_not_overwritten(self):
        (self.course / ".microgen_verified_completion.json").write_bytes(b"old")
        with self.assertRaisesRegex(p.PromotionError, "Already receipt"):
            self.prepare()
        self.assertFalse(self.package.exists())

    def test_rollback_on_failed_second_file_replace(self):
        self.prepare()
        second = self.second_backup()
        actual_replace = p.os.replace
        def failing_replace(src, dst):
            if str(dst).endswith("slides.mp4"):
                raise OSError("simulated cloud filesystem failure")
            return actual_replace(src, dst)
        with mock.patch.object(p, "verify_code"), \
             mock.patch.object(p, "DriveAssignedOwner") as owner, \
             mock.patch.object(p.os, "replace", side_effect=failing_replace):
            owner.return_value = mock.Mock(spec=["assert_held"])
            with self.assertRaisesRegex(OSError, "simulated"):
                p.promote(
                    self.course, self.package, second, section="2.2",
                    assignment=Path("assignment.json"),
                    assignment_sha="a" * 64, campaign_id="trial",
                    code_sha="b" * 40,
                    authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
        self.assertEqual(p.inventory(self.course), self.source_hashes)
        self.assertFalse((self.course / p.MARKER).exists())
        self.assertFalse(list(self.course.glob("*.microgen-*.candidate")))

    def test_success_requires_fresh_independent_destination_audit(self):
        self.prepare()
        second = self.second_backup()
        with mock.patch.object(p, "verify_code"), \
             mock.patch.object(p, "DriveAssignedOwner") as owner, \
             mock.patch.object(p, "legacy_receipt_valid", return_value=True):
            owner.return_value = mock.Mock(spec=["assert_held"])
            report = p.promote(
                self.course, self.package, second, section="2.2",
                assignment=Path("assignment.json"),
                assignment_sha="a" * 64, campaign_id="trial",
                code_sha="b" * 40,
                authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
        self.assertEqual(
            report["state"], "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION")
        self.assertTrue((self.package /
                         "promotion_pending_independent_audit.json").is_file())
        self.assertEqual(p.quality.sha256(self.course / "slides.pdf"),
                         self.pdf_sha)
        self.assertEqual(p.quality.sha256(self.course / "moodle_lecture.xml"),
                         self.source_hashes["moodle_lecture.xml"])
        self.assertFalse((self.course / ".microgen_verified_completion.json").exists())

    def test_complete_receipt_binds_source_and_candidate_evidence(self):
        import shutil
        self.prepare()
        dest = self.root / "synthetic_destination"
        shutil.copytree(self.course, dest)
        for name in ("slides.pdf", "slides.mp4", p.MARKER, p.EVIDENCE):
            shutil.copy2(self.package / "candidate" / name, dest / name)
        with mock.patch("microgen_legacy_video_repair.audio_stream_hash",
                        return_value="d" * 64), \
             mock.patch.object(p.quality, "check_slide_pdf",
                               return_value={"pages": 2}):
            self.assertTrue(p.legacy_receipt_valid(dest))
            (dest / p.EVIDENCE).write_bytes(b"changed audit")
            self.assertFalse(p.legacy_receipt_valid(dest))

    def test_independent_prepared_package_audit(self):
        import microgen_legacy_promotion_audit as audit
        self.prepare()
        state = audit.prepared_audit(self.package, self.course)
        self.assertEqual(state["state"], "PREPARED_BACKUP_VERIFIED_NO_PUBLICATION")
        self.assertFalse(state["publication_allowed"])
        (self.package / "original" / "source.pdf").write_bytes(b"drift")
        with self.assertRaisesRegex(p.PromotionError, "Backup"):
            audit.prepared_audit(self.package, self.course)

    def test_independent_destination_audit_detects_unrelated_drift(self):
        import microgen_legacy_promotion_audit as audit
        self.prepare()
        independent = self.second_backup()
        with mock.patch.object(p, "verify_code"), \
             mock.patch.object(p, "DriveAssignedOwner") as owner, \
             mock.patch.object(p, "legacy_receipt_valid", return_value=True):
            owner.return_value = mock.Mock(spec=["assert_held"])
            p.promote(self.course, self.package, independent,
                      section="2.2", assignment=Path("assignment.json"),
                      assignment_sha="a" * 64, campaign_id="trial",
                      code_sha="b" * 40,
                      authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
        m = json.loads((self.package / "package_manifest.json").read_text())
        with mock.patch("microgen_legacy_video_repair.audio_stream_hash",
                        return_value="d" * 64), \
             mock.patch.object(p.quality, "check_slide_pdf", return_value={"pages": 2}):
            params = {
                "expected_pdf_sha256": m["candidate_pdf_sha256"],
                "expected_mp4_sha256": m["candidate_mp4_sha256"],
                "expected_receipt_sha256": m["candidate_receipt_sha256"]
            }
            self.assertEqual(audit.destination_audit(self.course, self.package, **params)["state"],
                             "INDEPENDENT_DESTINATION_TECHNICAL_AUDIT_PASS")
            (self.course / "moodle_lecture.xml").write_bytes(b"unexpected")
            with self.assertRaisesRegex(p.PromotionError, "Unrelated destination"):
                audit.destination_audit(self.course, self.package, **params)

    def test_receipt_rejects_tampering_and_no_v1_spoof(self):
        self.prepare()
        receipt = self.package / "candidate" / p.MARKER
        doc = json.loads(receipt.read_text())
        self.assertNotIn("wav_sha256", doc)
        doc["schema_version"] = 1
        receipt.write_text(json.dumps(doc))
        with mock.patch.object(p.quality, "check_slide_pdf"):
            self.assertFalse(p.legacy_receipt_valid(self.package / "candidate"))

    def test_snapshot_case_collision_rejected(self):
        with mock.patch.object(p.quality, "sha256", wraps=p.quality.sha256):
            # Distinctly named, case-clashing files possible on Linux.
            if __import__("os").name != "nt":
                (self.course / "figure 2.2.png").write_bytes(b"case collision")
                with self.assertRaisesRegex(p.PromotionError, "Case-insensitive"):
                    p.inventory(self.course)


if __name__ == "__main__":
    unittest.main()
