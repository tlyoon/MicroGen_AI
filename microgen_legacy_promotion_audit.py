#!/usr/bin/env python3
"""Independent, read-only audit of legacy visual promotion or prepared package.

Run on a DIFFERENT PC from the owner of the candidate-generation/promotion.
Never modifies the source or Moodle and never issues an academic approval.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import microgen_quality as quality
from microgen_legacy_promotion import (EVIDENCE, MARKER, PromotionError,
    legacy_receipt_valid, verify_package, verify_snapshot, encoded)


def prepared_audit(package: Path, course: Path) -> dict:
    m = verify_package(Path(package), Path(course))
    return {
        "section": m["section"],
        "state": "PREPARED_BACKUP_VERIFIED_NO_PUBLICATION",
        "original_inventory_sha256": m["original_inventory_sha256"],
        "candidate_pdf_sha256": m["candidate_pdf_sha256"],
        "candidate_mp4_sha256": m["candidate_mp4_sha256"],
        "candidate_receipt_sha256": m["candidate_receipt_sha256"],
        "backup_verified": True, "originals_unchanged": True,
        "publication_allowed": False,
    }


def await_expected_replica(course: Path, backup: Path, *,
                           expected_pdf_sha256: str, expected_mp4_sha256: str,
                           expected_receipt_sha256: str,
                           timeout_seconds: float,
                           poll_seconds: float = 2.0) -> None:
    """Boundedly wait ONLY for absent Drive-replicated files, never bad hashes.

    This is a read-only visibility barrier, not a replacement for destination_audit.
    Files already visible with unexpected content fail immediately. The full
    destination audit still revalidates the protected backup and all course files.
    """
    if not 0 <= timeout_seconds <= 300:
        raise PromotionError("Replication timeout must be between 0 and 300 seconds")
    if not 0 < poll_seconds <= 30:
        raise PromotionError("Replication polling interval must be in (0, 30] seconds")
    course, backup = Path(course), Path(backup)
    manifest = json.loads((backup / "package_manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("state") != "PREPARED_NOT_PUBLISHED"
        or Path(manifest["course"]).resolve() != course.resolve()):
        raise PromotionError("Wrong backup or course for replication barrier")
    pins = {
        "slides.pdf": ("candidate_pdf_sha256", expected_pdf_sha256),
        "slides.mp4": ("candidate_mp4_sha256", expected_mp4_sha256),
        MARKER: ("candidate_receipt_sha256", expected_receipt_sha256),
        EVIDENCE: ("candidate_evidence_sha256", manifest["candidate_evidence_sha256"]),
    }
    for name, (field, value) in pins.items():
        if manifest[field] != value:
            raise PromotionError(f"Unexpected immutable hash for {name}")
    deadline = time.monotonic() + timeout_seconds
    while True:
        pending = []
        for name, (_, digest) in pins.items():
            target = course / name
            if not target.is_file():
                pending.append(name)
                continue
            if quality.sha256(target) != digest:
                raise PromotionError(f"Replica checksum mismatch for {name}")
        if not pending:
            return
        if time.monotonic() >= deadline:
            raise PromotionError("Replication visibility deadline exceeded for: "
                                 + ", ".join(pending))
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))


def destination_audit(course: Path, backup: Path, *,
                      expected_pdf_sha256: str, expected_mp4_sha256: str,
                      expected_receipt_sha256: str) -> dict:
    """Verify exact old inventory preserved except specifically replaced visuals."""
    course, backup = Path(course), Path(backup)
    m = json.loads((backup / "package_manifest.json").read_text(encoding="utf-8"))
    if m["state"] != "PREPARED_NOT_PUBLISHED" or Path(m["course"]).resolve() != course.resolve():
        raise PromotionError("Wrong backup or course")
    expected_old = m["original_files"]
    verify_snapshot(backup / "original", expected_old)
    if (m["candidate_pdf_sha256"] != expected_pdf_sha256
        or m["candidate_mp4_sha256"] != expected_mp4_sha256
        or m["candidate_receipt_sha256"] != expected_receipt_sha256):
        raise PromotionError("Proposed destination hashes do not match immutable package")
    if not legacy_receipt_valid(course):
        raise PromotionError("Missing, tampered, or invalid legacy visual receipt")
    if quality.sha256(course / MARKER) != expected_receipt_sha256:
        raise PromotionError("Receipt mismatch")
    if quality.sha256(course / "slides.pdf") != expected_pdf_sha256:
        raise PromotionError("Corrected PDF mismatch")
    if quality.sha256(course / "slides.mp4") != expected_mp4_sha256:
        raise PromotionError("Corrected MP4 mismatch")
    if quality.sha256(course / EVIDENCE) != m["candidate_evidence_sha256"]:
        raise PromotionError("Video evidence changed")
    present = {
        f.relative_to(course).as_posix(): quality.sha256(f)
        for f in course.rglob("*") if f.is_file()
    }
    new_expected = {**expected_old,
        "slides.pdf": expected_pdf_sha256,
        "slides.mp4": expected_mp4_sha256,
        MARKER: expected_receipt_sha256,
        EVIDENCE: m["candidate_evidence_sha256"]}
    if present != new_expected:
        different = sorted(set(present) ^ set(new_expected))
        changed = [n for n in present.keys() & new_expected.keys()
                   if present[n] != new_expected[n]]
        raise PromotionError(f"Unrelated destination files altered: files={different}, hashes={changed}")
    return {
        "section": m["section"],
        "state": "INDEPENDENT_DESTINATION_TECHNICAL_AUDIT_PASS",
        "backup_inventory_sha256": m["original_inventory_sha256"],
        "corrected_pdf_sha256": expected_pdf_sha256,
        "corrected_mp4_sha256": expected_mp4_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "source_figure_narration_quiz_hashes_preserved": True,
        "independent_review_not_academic_signoff": True,
        "moodle_published": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--course", type=Path, required=True)
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--destination-audit", action="store_true")
    p.add_argument("--pdf-sha256")
    p.add_argument("--mp4-sha256")
    p.add_argument("--receipt-sha256")
    p.add_argument("--write-report", type=Path)
    p.add_argument("--replication-wait-seconds", type=float, default=0.0,
                   help="Optional bounded read-only wait for missing Drive replica files (0-300s)")
    args = p.parse_args()
    if args.destination_audit:
        if not all((args.pdf_sha256, args.mp4_sha256, args.receipt_sha256)):
            p.error("Destination audit requires 3 pinned hashes")
        if args.replication_wait_seconds:
            await_expected_replica(
                args.course, args.package,
                expected_pdf_sha256=args.pdf_sha256,
                expected_mp4_sha256=args.mp4_sha256,
                expected_receipt_sha256=args.receipt_sha256,
                timeout_seconds=args.replication_wait_seconds)
        result = destination_audit(
            args.course, args.package, expected_pdf_sha256=args.pdf_sha256,
            expected_mp4_sha256=args.mp4_sha256,
            expected_receipt_sha256=args.receipt_sha256)
    else:
        if args.replication_wait_seconds:
            p.error("Replication visibility waiting is only valid for destination audits")
        result = prepared_audit(args.package, args.course)
    if args.write_report:
        if args.write_report.exists() or args.course.resolve() in args.write_report.resolve().parents:
            raise PromotionError("Refuse to overwrite or write audit into production course")
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_bytes(encoded(result))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
