"""Private incremental campaign tests use entirely fabricated evidence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from microgen_portable_private_authoring_gate import canonical_hash
from microgen_private_incremental_campaign import (
    IncrementalCampaignError, plan_incremental_campaign,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf8")


def fixture(root):
    src = root / "s" / "source.pdf"
    src.parent.mkdir()
    src.write_bytes(b"fake source evidence")
    packet = root / "s" / "packet.json"
    draft = root / "s" / "draft.json"
    write_json(packet, {"value": 1})
    write_json(draft, {"value": 2})
    stage = root / "s" / "stage"
    write_json(stage / "contract.json", {"contract": 1})
    write_json(stage / "narration.json", {"narration": 1})
    case = {"section_id": "1.2", "source_pdf": str(src),
            "private_packet": str(packet), "private_draft": str(draft),
            "stage": str(stage)}
    root_receipts = root / "receipt"
    science = {
        "section_records": [{
            "section_id": "1.2", "original_pdf_sha256": sha(src),
            "contract_sha256": sha(stage / "contract.json"),
            "narration_sha256": sha(stage / "narration.json"),
        }]
    }
    coverage = {
        "section_records": [{
            "section_id": "1.2", "source_pdf_sha256": sha(src),
            "private_packet_sha256": canonical_hash(json.loads(packet.read_text())),
            "private_draft_sha256": canonical_hash(json.loads(draft.read_text())),
        }]
    }
    sf = root_receipts / "science" / "multisection_private_science_receipt.json"
    cf = root_receipts / "coverage" / "multisection_private_coverage_receipt.json"
    write_json(sf, science)
    write_json(cf, coverage)
    write_json(root_receipts / "unified_private_campaign_receipt.json", {
        "sections": [{"section_id": "1.2"}],
        "coverage_receipt_sha256": sha(cf),
        "science_receipt_sha256": sha(sf),
    })
    return case, root_receipts, cf


class IncrementalTests(unittest.TestCase):
    def test_matching_receipts_preserve_existing_evidence_only(self):
        with tempfile.TemporaryDirectory() as td:
            case, receipt, _ = fixture(Path(td))
            result = plan_incremental_campaign([case], receipt)
            self.assertEqual(result["sections"][0]["decision"],
                             "TRACKED_INPUTS_UNCHANGED_PRESERVE_RECEIPT")
            self.assertFalse(result["untracked_stage_plan_figures_render_and_code_revalidated"])
            self.assertFalse(result["publication_allowed"])

    def test_changed_draft_revalidates_only_affected_section(self):
        with tempfile.TemporaryDirectory() as td:
            case, receipt, _ = fixture(Path(td))
            Path(case["private_draft"]).write_text('{"value":3}', encoding="utf8")
            result = plan_incremental_campaign([case], receipt)
            self.assertEqual(result["sections"][0]["changed_inputs"], ["private_draft"])
            self.assertEqual(result["sections"][0]["decision"],
                             "CHANGED_INPUT_REVALIDATE_SECTION")

    def test_missing_and_new_are_distinguished(self):
        with tempfile.TemporaryDirectory() as td:
            case, receipt, _ = fixture(Path(td))
            Path(case["private_packet"]).unlink()
            new = dict(case, section_id="1.3")
            result = plan_incremental_campaign([case, new], receipt)
            self.assertEqual(result["sections"][0]["missing_inputs"], ["private_packet"])
            self.assertEqual(result["sections"][1]["decision"],
                             "NEW_SECTION_REQUIRES_FULL_GATES")

    def test_receipt_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            case, receipt, coverage = fixture(Path(td))
            coverage.write_text('{"section_records":[]}', encoding="utf8")
            with self.assertRaises(IncrementalCampaignError):
                plan_incremental_campaign([case], receipt)

    def test_duplicate_cases_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            case, receipt, _ = fixture(Path(td))
            with self.assertRaises(IncrementalCampaignError):
                plan_incremental_campaign([case, case], receipt)


if __name__ == "__main__":
    unittest.main()
