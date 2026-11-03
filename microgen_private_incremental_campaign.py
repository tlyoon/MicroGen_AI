"""Private read-only planning against previously verified cross-section receipts.

No PDFs are repaired or re-rendered. A matching receipt only confirms the exact
tracked artifacts; untracked stage elements still require their normal gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from microgen_portable_private_authoring_gate import canonical_hash


class IncrementalCampaignError(ValueError):
    pass


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise IncrementalCampaignError("Expected a regular private manifest or receipt")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise IncrementalCampaignError("Expected JSON object")
    return data


def _hash(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def plan_incremental_campaign(cases: list, previous_receipt_dir: Path) -> dict:
    """Compare original evidence to signed-by-content prior receipts, fail closed.

    Nothing is declared fully validated because stage plan, rendered PDF,
    figures and current code version are outside the tracked identities.
    """
    root = Path(previous_receipt_dir)
    combined = _read(root / "unified_private_campaign_receipt.json")
    coverage_file = root / "coverage" / "multisection_private_coverage_receipt.json"
    science_file = root / "science" / "multisection_private_science_receipt.json"
    if (_hash(coverage_file) != combined.get("coverage_receipt_sha256")
            or _hash(science_file) != combined.get("science_receipt_sha256")):
        raise IncrementalCampaignError("Historical receipt identity mismatch")
    coverage = _read(coverage_file)
    science = _read(science_file)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 12:
        raise IncrementalCampaignError("Between one and twelve sections required")
    if not isinstance(combined.get("sections"), list):
        raise IncrementalCampaignError("Malformed unified receipt")
    def indexed(items):
        if not isinstance(items, list):
            raise IncrementalCampaignError("Invalid prior section records")
        rows = {v["section_id"]: v for v in items
                if isinstance(v, dict) and isinstance(v.get("section_id"), str)}
        if len(rows) != len(items):
            raise IncrementalCampaignError("Duplicate or invalid prior section ID")
        return rows
    old = indexed(combined["sections"])
    c_rows = indexed(coverage.get("section_records"))
    s_rows = indexed(science.get("section_records"))
    if set(old) != set(c_rows) or set(old) != set(s_rows):
        raise IncrementalCampaignError("Prior independent receipts disagree")
    seen = set()
    rows = []
    keys = {
        "source_pdf": ("source_pdf_sha256", "original_pdf_sha256"),
        "private_packet": ("private_packet_sha256", None),
        "private_draft": ("private_draft_sha256", None),
        "contract": (None, "contract_sha256"),
        "narration": (None, "narration_sha256"),
    }
    for item in cases:
        if not isinstance(item, dict) or set(item) != {
                "section_id", "source_pdf", "private_packet",
                "private_draft", "stage"}:
            raise IncrementalCampaignError("Malformed input case")
        sid = item["section_id"]
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,30}", sid) or sid in seen:
            raise IncrementalCampaignError("Invalid or duplicate section")
        seen.add(sid)
        if sid not in old:
            rows.append({"section_id": sid, "decision": "NEW_SECTION_REQUIRES_FULL_GATES",
                         "changed_inputs": [], "missing_inputs": []})
            continue
        paths = {k: Path(item[k]) for k in (
            "source_pdf", "private_packet", "private_draft")}
        stage = Path(item["stage"])
        paths.update(contract=stage / "contract.json", narration=stage / "narration.json")
        changed, missing = [], []
        for name, path in paths.items():
            measured = (_hash(path) if name not in ('private_packet', 'private_draft')
                        else canonical_hash(_read(path)) if path.is_file() and not path.is_symlink()
                        else None)
            left, right = keys[name]
            expected = (c_rows[sid].get(left) if left else s_rows[sid].get(right))
            if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
                raise IncrementalCampaignError("Previous evidence is incomplete")
            if measured is None:
                missing.append(name)
            elif measured != expected:
                changed.append(name)
        if missing:
            decision = "MISSING_INPUT_RESTORE_BEFORE_REVALIDATION"
        elif changed:
            decision = "CHANGED_INPUT_REVALIDATE_SECTION"
        else:
            decision = "TRACKED_INPUTS_UNCHANGED_PRESERVE_RECEIPT"
        rows.append({"section_id": sid, "decision": decision,
                     "changed_inputs": changed, "missing_inputs": missing})
    return {
        "schema_version": 1, "sections": rows,
        "previous_verified_sections": len(old),
        "tracked_identity_fields": list(keys),
        "untracked_stage_plan_figures_render_and_code_revalidated": False,
        "complete_scientific_semantics_proven": False,
        "provider_calls": 0, "source_files_modified": False,
        "publication_allowed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--previous-private-receipt-dir", type=Path, required=True)
    opts = parser.parse_args(argv)
    result = plan_incremental_campaign(
        _read(opts.private_manifest).get("cases"),
        opts.previous_private_receipt_dir)
    # Never print paths, hashes, source text or authored narration.
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
