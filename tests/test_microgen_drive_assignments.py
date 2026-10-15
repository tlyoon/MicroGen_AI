"""Drive-manifest assignment tests: no Google Cloud Storage dependency."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_drive_assignments as d
from microgen_ownership import LeaseLost


class DriveAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        self.path = Path(self.tmp.name) / "assignment.json"
        self.manifest = {
            "schema_version": 1,
            "campaign_id": "isolated-2026",
            "source_root": str(self.root),
            "participants": ["HP", "DELL-115", "YOGA6"],
            "owners": {"8.4": "HP", "8.5": "DELL-115", "8.6": "YOGA6"},
        }
        self.write()
        self.host = mock.patch.object(d.socket, "gethostname", return_value="HP")
        self.host.start()
        self.addCleanup(self.host.stop)

    def write(self):
        self.path.write_text(json.dumps(self.manifest, sort_keys=True, indent=2),
                             encoding="utf-8")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def owner(self, target="8.4", digest=None):
        return d.DriveAssignedOwner(
            self.path, self.sha if digest is None else digest,
            "isolated-2026", self.root, target,
        )

    def test_correct_host_acquires(self):
        with self.owner() as lease:
            lease.assert_held()

    def test_wrong_host_fails_closed(self):
        with self.assertRaises(d.AssignmentDenied):
            self.owner("8.5").assert_held()

    def test_missing_target_fails_closed(self):
        with self.assertRaises(d.AssignmentDenied):
            self.owner("9.1").assert_held()

    def test_removed_manifest_loses_ownership(self):
        lease = self.owner()
        lease.assert_held()
        self.path.unlink()
        with self.assertRaises(LeaseLost):
            lease.assert_held()

    def test_modified_manifest_invalidates_running_worker(self):
        lease = self.owner()
        lease.assert_held()
        self.manifest["owners"]["8.4"] = "DELL-115"
        self.write()
        with self.assertRaisesRegex(LeaseLost, "SHA256"):
            lease.assert_held()

    def test_stale_pin_fails_closed(self):
        with self.assertRaises(LeaseLost):
            self.owner(digest="a" * 64).assert_held()

    def test_source_root_must_match(self):
        other = self.root.parent / "different"
        other.mkdir()
        with self.assertRaisesRegex(LeaseLost, "Source root"):
            d.DriveAssignedOwner(self.path, self.sha, "isolated-2026",
                                 other, "8.4").assert_held()

    def test_campaign_must_match(self):
        with self.assertRaisesRegex(LeaseLost, "Campaign"):
            d.DriveAssignedOwner(self.path, self.sha, "wrong-campaign",
                                 self.root, "8.4").assert_held()

    def test_duplicate_participant_rejected(self):
        self.manifest["participants"].append("HP")
        self.write()
        with self.assertRaisesRegex(LeaseLost, "Duplicate"):
            self.owner().assert_held()

    def test_invalid_or_unregistered_owner_rejected(self):
        self.manifest["owners"]["8.4"] = "UNKNOWN"
        self.write()
        with self.assertRaises(LeaseLost):
            self.owner().assert_held()

    def test_host_cannot_be_overridden(self):
        with self.assertRaisesRegex(d.AssignmentError, "spoofing"):
            d.DriveAssignedOwner(self.path, self.sha, "isolated-2026",
                                 self.root, "8.4", host="DELL-115")

    def test_no_external_gcs_required(self):
        # Supplying a valid assignment only needs the stdlib and existing
        # ownership exception class, no live Google credentials or API.
        with mock.patch.dict("sys.modules", {"google.cloud.storage": None}):
            self.owner().assert_held()


if __name__ == "__main__":
    unittest.main()
