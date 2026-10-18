"""No-production tests for owner-pinned resumable legacy release workflow."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_release_coordinator as c


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.course_root = self.root / "course"
        self.course = self.course_root / "1" / "1.3"
        self.course.mkdir(parents=True)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.assignment = self.root / "owners.json"
        self.assignment.write_text('{"owners":{"1.3":"DELL-115"}}')
        self.secondary = self.root / "second"
        self.evidence = self.root / "evidence"
        self.manifest_path = self.root / "plan.json"
        self.plan = {
            "schema_version": 1, "campaign_id": "thomas-1-3-test",
            "section": "1.3", "source_root": str(self.course_root),
            "candidate_dir": str(self.candidate),
            "candidate_pdf_sha256": "a" * 64,
            "assignment_path": str(self.assignment),
            "assignment_sha256": hashlib.sha256(self.assignment.read_bytes()).hexdigest(),
            "code_commit": "b" * 40, "package_tag": "1_3_test",
            "secondary_package": str(self.secondary),
            "reviewers": ["HP", "YOGA6"], "evidence_dir": str(self.evidence),
        }
        self.manifest_path.write_text(json.dumps(self.plan))
        self.sha = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.paths = c.locations(self.plan)
        self.paths['primary'] = self.root / 'primary'

    def test_pinned_plan_requires_exact_hash_and_schema(self):
        self.assertEqual(c.pinned_plan(self.manifest_path, self.sha), self.plan)
        with self.assertRaisesRegex(c.CoordinationError, "changed"):
            c.pinned_plan(self.manifest_path, "0" * 64)
        self.plan["unexpected"] = True
        self.manifest_path.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(c.CoordinationError, "Invalid or unexpected"):
            c.pinned_plan(self.manifest_path, hashlib.sha256(self.manifest_path.read_bytes()).hexdigest())

    def test_no_spoofed_reviewer_or_unregistered_completer(self):
        with mock.patch.object(c, "machine_id", return_value="DELL-115"):
            with self.assertRaisesRegex(c.CoordinationError, "not a designated"):
                c.require_reviewer(self.plan)
        with mock.patch.object(c, "machine_id", return_value="HP"):
            c.require_reviewer(self.plan)

    def test_save_once_is_idempotent_and_refuses_conflicting_checkpoint(self):
        item = c.evidence(self.plan, self.paths, "audit-backup", "HP", self.sha,
                          {"status": "INDEPENDENT_BACKUP_PASS"})
        loc = c.record_path(self.paths, "audit-backup", "HP")
        c.save_once(loc, item)
        c.save_once(loc, item)
        self.assertEqual(c.verified_record(self.plan, self.paths, "audit-backup",
                                           "HP", self.sha)["status"], "INDEPENDENT_BACKUP_PASS")
        with self.assertRaisesRegex(c.CoordinationError, "conflicts"):
            c.save_once(loc, {**item, "details": {"status": "FAIL"}})

    def test_stale_or_altered_receipt_is_rejected(self):
        x = c.evidence(self.plan, self.paths, "promote", "DELL-115",
                       self.sha, {"status": "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION"})
        p = c.record_path(self.paths, "promote", "DELL-115")
        c.save_once(p, x)
        self.assertEqual(c.verified_record(self.plan, self.paths, "promote",
                                           "DELL-115", self.sha)["status"],
                         "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION")
        x["plan_sha256"] = "0" * 64
        p.write_bytes(c.encoded(x))
        with self.assertRaisesRegex(c.CoordinationError, "stale"):
            c.verified_record(self.plan, self.paths, "promote", "DELL-115", self.sha)

    def test_status_does_not_write_or_claim_moodle_publication(self):
        with mock.patch.object(c, "owner_name_from_assignment", return_value="DELL-115"):
            report = c.status(self.plan, self.paths, self.sha)
        self.assertFalse(report["production_publication_automated"])
        self.assertEqual(report["phases"]["promote"]["DELL-115"], "PENDING")
        self.assertEqual(report["phases"]["audit-backup"]["HP"], "PENDING")
        self.assertFalse(self.evidence.exists())

    def test_owner_phase_preflight_checks_claim_and_candidate(self):
        info = {"status": "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW",
                "source_provenance": {"ok": True}}
        with mock.patch.object(c, "ensure_pin_and_code"), \
             mock.patch.object(c, "claimed_owner") as owner, \
             mock.patch.object(c, "check_candidate", return_value=info), \
             mock.patch.object(c, "machine_id", return_value="DELL-115"):
            record = c.execute(self.plan, self.paths, self.sha, "preflight")
        owner.assert_called_once()
        self.assertEqual(record["details"]["status"], info["status"])
        self.assertTrue(c.record_path(self.paths, "preflight", "DELL-115").exists())

    def test_unauthorized_production_is_blocked_before_action(self):
        with mock.patch.object(c, "ensure_pin_and_code"), \
             mock.patch.object(c, "claimed_owner"), \
             mock.patch.object(c, "machine_id", return_value="DELL-115"), \
             mock.patch.object(c, "promote") as production:
            with self.assertRaisesRegex(c.CoordinationError, "authorization missing"):
                c.execute(self.plan, self.paths, self.sha, "promote")
            production.assert_not_called()

    def test_backups_need_independent_verified_reviewers(self):
        manifest = {"original_inventory_sha256": "c" * 64,
                    "candidate_receipt_sha256": "d" * 64,
                    "candidate_pdf_sha256": "a" * 64,
                    "candidate_mp4_sha256": "e" * 64}
        with mock.patch.object(c, "ensure_pin_and_code"), \
             mock.patch.object(c, "claimed_owner"), \
             mock.patch.object(c, "machine_id", return_value="DELL-115"), \
             mock.patch.object(c, "verify_package", return_value=manifest), \
             mock.patch.object(c, "promote") as production:
            with self.assertRaises(FileNotFoundError):
                c.execute(self.plan, self.paths, self.sha, "promote",
                          authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
            production.assert_not_called()
            for host in self.plan["reviewers"]:
                c.save_once(c.record_path(self.paths, "audit-backup", host),
                            c.evidence(self.plan, self.paths, "audit-backup", host, self.sha,
                                       {"status":"INDEPENDENT_BACKUP_PASS",
                                        "inventory_sha256":"f" * 64,
                                        "receipt_sha256":"d" * 64}))
            with self.assertRaisesRegex(c.CoordinationError, "does not match"):
                c.execute(self.plan, self.paths, self.sha, "promote",
                          authorization="AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT")
            production.assert_not_called()

    def test_crash_recovery_never_invokes_production_replace(self):
        self.paths["primary"].mkdir(parents=True)
        receipt = {
            "state": "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION",
            "pdf_sha256": "a" * 64, "mp4_sha256": "e" * 64,
            "receipt_sha256": "d" * 64
        }
        (self.paths["primary"] / "promotion_pending_independent_audit.json").write_text(json.dumps(receipt))
        manifest = {"candidate_pdf_sha256": "a" * 64,
                    "candidate_mp4_sha256": "e" * 64,
                    "candidate_receipt_sha256": "d" * 64}
        self.secondary.mkdir()
        (self.secondary / "package_manifest.json").write_text(json.dumps(manifest))
        with mock.patch.object(c, "ensure_pin_and_code"), \
             mock.patch.object(c, "claimed_owner") as owner, \
             mock.patch.object(c, "machine_id", return_value="DELL-115"), \
             mock.patch.object(c, "destination_audit", return_value={
                 "corrected_pdf_sha256": "a" * 64,
                 "corrected_mp4_sha256": "e" * 64,
                 "receipt_sha256": "d" * 64
             }), mock.patch.object(c, "promote") as production:
            owner.return_value = mock.Mock(spec=['assert_held'])
            c.execute(self.plan, self.paths, self.sha, "recover-promote")
            production.assert_not_called()
            owner.return_value.assert_held.assert_called()
        self.assertTrue(c.record_path(self.paths, "promote", "DELL-115").exists())

    def test_completion_requires_both_reviewers_and_exact_pins(self):
        m = {"original_inventory_sha256":"c"*64,
             "candidate_pdf_sha256":"a"*64,
             "candidate_mp4_sha256":"e"*64,
             "candidate_receipt_sha256":"d"*64}
        self.secondary.mkdir()
        (self.secondary / "package_manifest.json").write_text(json.dumps(m))
        with mock.patch.object(c, "ensure_pin_and_code"), \
             mock.patch.object(c, "claimed_owner"), \
             mock.patch.object(c, "machine_id", return_value="DELL-115"), \
             mock.patch.object(c, "destination_audit", return_value={}):
            for reviewer in self.plan["reviewers"]:
                c.save_once(c.record_path(self.paths, "audit-destination", reviewer),
                            c.evidence(self.plan, self.paths, "audit-destination", reviewer,
                                       self.sha, {"status":"INDEPENDENT_DESTINATION_TECHNICAL_AUDIT_PASS",
                                        "inventory_sha256":"c"*64, "pdf_sha256":"a"*64,
                                        "mp4_sha256":"e"*64, "receipt_sha256":"d"*64}))
            result=c.execute(self.plan,self.paths,self.sha,"complete")
            self.assertIn("NOT_MOODLE_PUBLISHED",result["details"]["status"])


if __name__ == "__main__":
    unittest.main()
