"""Test Drive replication readiness without confusing missing files with tampering."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_promotion_audit as audit
from microgen_legacy_promotion import EVIDENCE, MARKER, PromotionError


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReplicationBarrierTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.course = self.root / "course" / "1" / "1.5"
        self.course.mkdir(parents=True)
        self.backup = self.root / "backups"
        self.backup.mkdir()
        self.payloads = {
            "slides.pdf": b"accepted-corrected-pdf",
            "slides.mp4": b"accepted-original-aac-video",
            MARKER: b"accepted-v2-receipt",
            EVIDENCE: b"accepted-video-qa-evidence",
        }
        self.pins = {
            "expected_pdf_sha256": sha(self.payloads["slides.pdf"]),
            "expected_mp4_sha256": sha(self.payloads["slides.mp4"]),
            "expected_receipt_sha256": sha(self.payloads[MARKER]),
        }
        manifest = {
            "state": "PREPARED_NOT_PUBLISHED",
            "course": str(self.course),
            "candidate_pdf_sha256": self.pins["expected_pdf_sha256"],
            "candidate_mp4_sha256": self.pins["expected_mp4_sha256"],
            "candidate_receipt_sha256": self.pins["expected_receipt_sha256"],
            "candidate_evidence_sha256": sha(self.payloads[EVIDENCE]),
        }
        (self.backup / "package_manifest.json").write_text(json.dumps(manifest))
        for name, value in self.payloads.items():
            (self.course / name).write_bytes(value)

    def run_check(self, timeout=0.05):
        return audit.await_expected_replica(
            self.course, self.backup, timeout_seconds=timeout,
            poll_seconds=0.005, **self.pins)

    def test_all_files_present_does_not_sleep(self):
        with mock.patch.object(audit.time, "sleep") as sleeping:
            self.run_check()
            sleeping.assert_not_called()

    def test_missing_receipt_reappears_after_bounded_poll(self):
        (self.course / MARKER).unlink()
        original_sleep = audit.time.sleep
        def sync_after_one_poll(seconds):
            (self.course / MARKER).write_bytes(self.payloads[MARKER])
        with mock.patch.object(audit.time, "sleep", side_effect=sync_after_one_poll) as sleeper:
            self.run_check()
            self.assertEqual(sleeper.call_count, 1)
        self.assertEqual((self.course / MARKER).read_bytes(), self.payloads[MARKER])

    def test_missing_receipt_times_out_without_writing_any_files(self):
        (self.course / MARKER).unlink()
        before = {p.name: p.read_bytes() for p in self.course.iterdir() if p.is_file()}
        with self.assertRaisesRegex(PromotionError, "visibility deadline exceeded"):
            self.run_check(timeout=0.02)
        self.assertFalse((self.course / MARKER).exists())
        self.assertEqual(before, {
            p.name: p.read_bytes() for p in self.course.iterdir() if p.is_file()
        })

    def test_wrong_hash_fails_immediately_not_silently_retried(self):
        (self.course / MARKER).write_bytes(b"tampered receipt")
        with mock.patch.object(audit.time, "sleep") as sleeper:
            with self.assertRaisesRegex(PromotionError, "Replica checksum mismatch"):
                self.run_check(timeout=0.2)
            sleeper.assert_not_called()

    def test_bad_pinned_manifest_or_course_blocks(self):
        m = self.backup / "package_manifest.json"
        d = json.loads(m.read_text())
        d["candidate_receipt_sha256"] = sha(b"other")
        m.write_text(json.dumps(d))
        with self.assertRaisesRegex(PromotionError, "Unexpected immutable hash"):
            self.run_check()
        d["candidate_receipt_sha256"] = self.pins["expected_receipt_sha256"]
        d["course"] = str(self.root / "other_course")
        m.write_text(json.dumps(d))
        with self.assertRaisesRegex(PromotionError, "Wrong backup or course"):
            self.run_check()

    def test_wait_cannot_be_unlimited_or_negative(self):
        for timeout in (-1, 301):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(PromotionError, "between 0 and 300"):
                    self.run_check(timeout=timeout)


if __name__ == "__main__":
    unittest.main()
