"""Offline tests: hash-pinned fixed owners, local FIFO and no silent release."""
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_video_batch as b


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "course"
        self.source.mkdir()
        self.pdfs = self.root / "pdfs"
        self.pdfs.mkdir()
        self.mp4s = self.root / "video"
        self.owner = socket.gethostname().upper()
        self.sec = "1.2"
        self.folder = self.source / "1" / self.sec
        self.folder.mkdir(parents=True)
        (self.folder / "slides.mp4").write_bytes(b"source mp4")
        (self.folder / "slides.pdf").write_bytes(b"source pdf")
        self.pdf = self.pdfs / "1_2" / "slides.pdf"
        self.pdf.parent.mkdir()
        self.pdf.write_bytes(b"verified source-based pdf candidate")
        self.manifest = self.root / "owners.json"
        self.candidates = self.root / "candidates.json"
        self.set_owners({self.sec: self.owner})
        self.set_candidates()

    @staticmethod
    def hexfile(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def set_owners(self, owners):
        self.manifest.write_text(json.dumps({
            "schema_version": 1, "campaign_id": "test-campaign",
            "source_root": str(self.source.resolve()),
            "participants": [self.owner, "ANOTHER-HOST"],
            "owners": owners
        }), encoding="utf-8")
        self.owner_sha = self.hexfile(self.manifest)

    def set_candidates(self):
        self.candidates.write_text(json.dumps({
            "schema_version": 1,
            "sections": [{"section": self.sec, "status": "TECHNICAL_PDF_CANDIDATE_PASS",
                          "new_pdf_sha256": self.hexfile(self.pdf)}]
        }), encoding="utf-8")
        self.candidate_sha = self.hexfile(self.candidates)

    def call(self, execute=False, targets=None):
        return b.campaign(
            manifest=self.manifest, manifest_sha=self.owner_sha,
            candidate_manifest=self.candidates, candidate_sha=self.candidate_sha,
            campaign_id="test-campaign", source_root=self.source,
            pdf_root=self.pdfs, output_root=self.mp4s,
            targets=targets or [self.sec], code_commit="1" * 40,
            execute=execute,
        )

    def test_read_only_preflight_requires_immutable_manifest_and_owner(self):
        with mock.patch.object(b, "verify_code"):
            result = self.call()
            self.assertEqual(result["items"][0]["status"], "READY_FOR_CANDIDATE_RENDER")
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(self.mp4s.exists())
            (self.manifest).write_text(self.manifest.read_text() + " ")
            with self.assertRaisesRegex(b.BatchError, "Pinned file differs"):
                self.call()
            self.set_owners({self.sec: "ANOTHER-HOST"})
            with self.assertRaisesRegex(Exception, "assigned to"):
                self.call()

    def test_code_and_candidate_hashes_must_be_pinned(self):
        with mock.patch.object(b, "verify_code"):
            self.pdf.write_bytes(b"tampered")
            with self.assertRaisesRegex(b.BatchError, "drift"):
                self.call()
            self.pdf.write_bytes(b"verified source-based pdf candidate")
            self.candidates.write_text(self.candidates.read_text() + " ")
            with self.assertRaisesRegex(b.BatchError, "Pinned file differs"):
                self.call()
            self.set_candidates()
            with self.assertRaisesRegex(b.BatchError, "unique"):
                self.call(targets=[self.sec, self.sec])

    def test_no_untracked_targets_and_no_drive_output(self):
        with mock.patch.object(b, "verify_code"):
            with self.assertRaisesRegex(b.BatchError, "Unverified target"):
                self.call(targets=["5.9"])
            with self.assertRaisesRegex(b.BatchError, "local disk"):
                b.campaign(
                    manifest=self.manifest, manifest_sha=self.owner_sha,
                    candidate_manifest=self.candidates, candidate_sha=self.candidate_sha,
                    campaign_id="test-campaign", source_root=self.source,
                    pdf_root=self.pdfs, output_root=self.root.parent / "My Drive" / "videos",
                    targets=[self.sec], code_commit="1" * 40,
                )

    def test_local_lock_is_exclusive_and_not_auto_reclaimed(self):
        self.mp4s.mkdir()
        with b.LocalExclusiveRun(self.mp4s):
            with self.assertRaisesRegex(b.BatchError, "Another worker"):
                with b.LocalExclusiveRun(self.mp4s):
                    pass
            self.assertTrue((self.mp4s / ".microgen_video_batch.lock").exists())
        self.assertFalse((self.mp4s / ".microgen_video_batch.lock").exists())

    def test_refuses_incomplete_outputs_or_old_report(self):
        self.mp4s.mkdir()
        folder = self.mp4s / "1_2"
        folder.mkdir()
        with mock.patch.object(b, "verify_code"):
            with self.assertRaisesRegex(b.BatchError, "Unverified previous output"):
                self.call()
        (folder / "video_repair_report.json").write_text(json.dumps({
            "status": "VIDEO_CANDIDATE_FAILED"
        }))
        (folder / "corrected_slides.mp4").write_bytes(b"garbage")
        with self.assertRaisesRegex(b.BatchError, "did not pass"):
            b.validate_completed(folder, expected_pdf_sha=self.hexfile(self.pdf),
                                 source=self.folder)

    def test_run_checks_ownership_before_and_after_each_child(self):
        class Owner:
            def __init__(self):
                self.calls = 0
            def assert_held(self):
                self.calls += 1
        owner = Owner()
        self.mp4s.mkdir()
        log = self.mp4s / "logs"
        log.mkdir()
        with mock.patch.object(b.subprocess, "Popen") as p, \
             mock.patch.object(b, "validate_completed", return_value={
                 "corrected_mp4_sha256": "1" * 64
             }):
            process = p.return_value
            process.poll.side_effect = [None, 0]
            process.returncode = 0
            data = b.run_one(
                source=self.folder, pdf=self.pdf, output=self.mp4s / "section_1_2",
                owner=owner, pdf_sha=self.hexfile(self.pdf),
                log_root=log, poll_seconds=0
            )
            self.assertEqual(data["status"], "NEW_CANDIDATE_PASS_NOT_PUBLISHED")
            self.assertGreaterEqual(owner.calls, 3)

    def test_planning_does_not_generate_or_publish(self):
        with mock.patch.object(b, "verify_code"), \
             mock.patch.object(b, "run_one") as run:
            self.call(execute=False)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
