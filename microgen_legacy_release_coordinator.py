#!/usr/bin/env python3
"""Fixed-owner, audited, resumable release coordinator for legacy visual lectures.

One explicit phase per CLI invocation. This does NOT auto-publish anything.
Evidence stored on a Drive replica is not a cryptographic remote signature;
the approved operator must independently confirm authorized reviewer identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from microgen_drive_assignments import DriveAssignedOwner, machine_id
from microgen_legacy_promotion import (
    PromotionError, encoded, prepare, promote, verify_package, verify_snapshot,
)
from microgen_legacy_promotion_audit import (
    await_expected_replica, destination_audit, prepared_audit,
)
from microgen_legacy_release_gate import inspect_release
from microgen_legacy_video_batch import verify_code, local_path, LocalExclusiveRun
from microgen_quality import sha256


class CoordinationError(RuntimeError):
    pass


PHASES = (
    "preflight", "prepare", "backup", "audit-backup",
    "promote", "recover-promote", "audit-destination", "complete", "status",
)
HOST_RE = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,79}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SECTION_RE = re.compile(r"\d+\.\d+\Z")


def pinned_plan(path: Path, digest: str) -> dict:
    if not SHA_RE.fullmatch(digest):
        raise CoordinationError("Explicit pinned plan SHA256 required")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise CoordinationError("Release plan has changed or differs on this Drive replica")
    plan = json.loads(content.decode("utf-8-sig"))
    expected = {
        "schema_version", "campaign_id", "section", "source_root", "candidate_dir",
        "candidate_pdf_sha256", "assignment_path", "assignment_sha256",
        "code_commit", "package_tag", "secondary_package", "reviewers",
        "evidence_dir",
    }
    if not isinstance(plan, dict) or set(plan) != expected or plan["schema_version"] != 1:
        raise CoordinationError("Invalid or unexpected release-plan fields")
    if not SECTION_RE.fullmatch(str(plan["section"])):
        raise CoordinationError("Section must be a numeric subchapter")
    if not SHA_RE.fullmatch(str(plan["candidate_pdf_sha256"])):
        raise CoordinationError("Invalid pinned candidate PDF hash")
    if not SHA_RE.fullmatch(str(plan["assignment_sha256"])):
        raise CoordinationError("Invalid assignment hash")
    if not COMMIT_RE.fullmatch(str(plan["code_commit"])):
        raise CoordinationError("Code commit must be full 40-digit SHA")
    reviewers = plan["reviewers"]
    if (not isinstance(reviewers, list) or len(reviewers) != 2
        or len(set(reviewers)) != len(reviewers)
        or any(not isinstance(h, str) or not HOST_RE.fullmatch(h) for h in reviewers)):
        raise CoordinationError("Exactly two distinct, valid independent reviewers required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", str(plan["package_tag"])):
        raise CoordinationError("Unsafe local package tag")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", str(plan["campaign_id"])):
        raise CoordinationError("Unsafe campaign identifier")
    return plan


def locations(plan: dict) -> dict[str, Path]:
    root = Path(plan["source_root"]).resolve()
    section = plan["section"]
    course = root / section.split(".")[0] / section
    candidate = Path(plan["candidate_dir"]).resolve()
    secondary = Path(plan["secondary_package"]).resolve()
    evidence_root = Path(plan["evidence_dir"]).resolve()
    for label, value in (("candidate", candidate), ("secondary backup", secondary),
                         ("phase evidence", evidence_root)):
        if value == root or root in value.parents or value in course.parents:
            raise CoordinationError(f"{label} may not be located inside the course source tree")
    if secondary == candidate or secondary in candidate.parents or candidate in secondary.parents:
        raise CoordinationError("Secondary backup and candidate input must not overlap")
    if evidence_root == secondary or evidence_root in secondary.parents or secondary in evidence_root.parents:
        raise CoordinationError("Evidence and backup roots must not overlap")
    return {
        "root": root,
        "course": course,
        "candidate": candidate,
        "primary": local_path(
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "MicroGen_ReleasePreparation_20261018" / plan["package_tag"],
            "Primary package"),
        "secondary": secondary,
        "evidence": evidence_root,
        "assignment": Path(plan["assignment_path"]).resolve(),
    }


def claimed_owner(plan: dict, paths: dict[str, Path]) -> DriveAssignedOwner:
    owner = DriveAssignedOwner(
        paths["assignment"], plan["assignment_sha256"], plan["campaign_id"],
        paths["root"], plan["section"],
    )
    owner.assert_held()
    if machine_id() in plan["reviewers"]:
        raise CoordinationError("Production owner cannot be an independent reviewer")
    return owner


def require_reviewer(plan: dict):
    if machine_id() not in plan["reviewers"]:
        raise CoordinationError("This host is not a designated independent reviewer")


def ensure_pin_and_code(plan: dict):
    verify_code(Path(__file__).resolve().parent, plan["code_commit"])


def record_path(paths: dict[str, Path], phase: str, host: str) -> Path:
    return paths["evidence"] / f'{phase}_{host}.json'


def evidence(plan: dict, paths: dict[str, Path], phase: str, host: str,
             plan_sha: str, details: dict) -> dict:
    return {
        "schema_version": 1, "campaign_id": plan["campaign_id"],
        "section": plan["section"], "plan_sha256": plan_sha,
        "phase": phase, "host": host, "code_commit": plan["code_commit"],
        "details": details, "moodle_published": False,
        "signed_academic_approval_created": False,
    }


def save_once(file: Path, record: dict) -> None:
    """Write-once per predetermined host and phase, never overwrite prior QA."""
    payload = encoded(record)
    file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        if file.read_bytes() != payload:
            raise CoordinationError(f"Existing phase receipt conflicts: {file}")
    # Drive replicas aren't atomic global locks: one producer is assigned
    # to each receipt path and all other PCs rehash the payload on read.


def verified_record(plan: dict, paths: dict[str, Path], phase: str,
                    host: str, plan_sha: str) -> dict:
    file = record_path(paths, phase, host)
    doc = json.loads(file.read_text(encoding="utf-8"))
    if set(doc) != {
        "schema_version", "campaign_id", "section", "plan_sha256",
        "phase", "host", "code_commit", "details", "moodle_published",
        "signed_academic_approval_created",
    }:
        raise CoordinationError("Stage receipt shape invalid")
    if (doc["schema_version"] != 1 or doc["campaign_id"] != plan["campaign_id"]
        or doc["section"] != plan["section"] or doc["plan_sha256"] != plan_sha
        or doc["code_commit"] != plan["code_commit"]
        or doc["phase"] != phase or doc["host"] != host
        or doc["moodle_published"] is not False
        or doc["signed_academic_approval_created"] is not False):
        raise CoordinationError("Foreign or stale phase evidence")
    return doc["details"]


def manifest_pins(manifest: dict) -> dict:
    return {
        "expected_pdf_sha256": manifest["candidate_pdf_sha256"],
        "expected_mp4_sha256": manifest["candidate_mp4_sha256"],
        "expected_receipt_sha256": manifest["candidate_receipt_sha256"],
    }


def check_candidate(plan: dict, paths: dict[str, Path]) -> dict:
    result = inspect_release(
        paths["course"], paths["candidate"] / "corrected_slides.pdf",
        paths["candidate"], expected_pdf_sha256=plan["candidate_pdf_sha256"],
        section=plan["section"],
    )
    if result["status"] != "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW":
        raise CoordinationError("Candidate release gate blocked: " + "; ".join(result["reasons"]))
    return result


def secondary_matches_primary(paths: dict[str, Path]) -> dict:
    manifest = json.loads((paths["primary"] / "package_manifest.json").read_text(encoding="utf-8"))
    second = json.loads((paths["secondary"] / "package_manifest.json").read_text(encoding="utf-8"))
    if encoded(manifest) != encoded(second):
        raise CoordinationError("Secondary manifest differs from primary")
    verify_snapshot(paths["secondary"] / "original", manifest["original_files"])
    for name, key in (
        ("slides.pdf", "candidate_pdf_sha256"),
        ("slides.mp4", "candidate_mp4_sha256"),
        (".microgen_legacy_visual_repair_receipt.json", "candidate_receipt_sha256"),
        (".microgen_legacy_video_evidence.json", "candidate_evidence_sha256"),
    ):
        if sha256(paths["secondary"] / "candidate" / name) != manifest[key]:
            raise CoordinationError(f"Secondary candidate differs: {name}")
    return manifest


def execute(plan: dict, paths: dict[str, Path], plan_sha: str, phase: str,
            *, authorization: str = "", replication_wait: float = 0.0) -> dict:
    if phase not in PHASES:
        raise CoordinationError(f"Invalid phase {phase}")
    if phase == "status":
        return status(plan, paths, plan_sha)
    # All changing phases and independent verification require identical code.
    ensure_pin_and_code(plan)
    host = machine_id()
    if phase in {"preflight", "prepare", "backup", "promote", "recover-promote", "complete"}:
        owner = claimed_owner(plan, paths)
    else:
        require_reviewer(plan) if phase in {"audit-backup", "audit-destination"} else None
        owner = None
    if phase == "preflight":
        info = check_candidate(plan, paths)
        details = {"status": info["status"], "candidate_pdf_sha256": plan["candidate_pdf_sha256"],
                   "source_provenance": info.get("source_provenance")}
    elif phase == "prepare":
        if paths["primary"].exists():
            manifest = verify_package(paths["primary"], paths["course"])
        else:
            check_candidate(plan, paths)
            manifest = prepare(
                paths["course"], paths["candidate"], paths["primary"],
                section=plan["section"], expected_pdf_sha=plan["candidate_pdf_sha256"],
            )
        if manifest["candidate_pdf_sha256"] != plan["candidate_pdf_sha256"]:
            raise CoordinationError("Prepared package has wrong corrected slide PDF")
        details = {"status": "PREPARED_NOT_PUBLISHED",
                   "original_inventory_sha256": manifest["original_inventory_sha256"],
                   "candidate_mp4_sha256": manifest["candidate_mp4_sha256"],
                   "receipt_sha256": manifest["candidate_receipt_sha256"]}
    elif phase == "backup":
        manifest = verify_package(paths["primary"], paths["course"])
        # Existing backup can only be resumed after exact independent recheck.
        if paths["secondary"].exists():
            secondary_matches_primary(paths)
        else:
            # shutil.copytree fails if a partial stale destination exists;
            # no deletion or replacement of forensic evidence.
            shutil.copytree(paths["primary"], paths["secondary"])
            secondary_matches_primary(paths)
        details = {"status": "TWO_FULL_BACKUPS_VERIFIED",
                   "inventory_sha256": manifest["original_inventory_sha256"],
                   "receipt_sha256": manifest["candidate_receipt_sha256"]}
    elif phase == "audit-backup":
        manifest = prepared_audit(paths["secondary"], paths["course"])
        details = {"status": "INDEPENDENT_BACKUP_PASS",
                   "inventory_sha256": manifest["original_inventory_sha256"],
                   "receipt_sha256": manifest["candidate_receipt_sha256"]}
    elif phase == "promote":
        if authorization != "AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT":
            raise CoordinationError("Explicit single-section production authorization missing")
        manifest = verify_package(paths["primary"], paths["course"])
        for reviewer in plan["reviewers"]:
            prior = verified_record(plan, paths, "audit-backup", reviewer, plan_sha)
            if (prior["status"] != "INDEPENDENT_BACKUP_PASS"
                or prior["inventory_sha256"] != manifest["original_inventory_sha256"]
                or prior["receipt_sha256"] != manifest["candidate_receipt_sha256"]):
                raise CoordinationError("Reviewer backup evidence does not match pinned package")
        secondary_matches_primary(paths)
        owner.assert_held()
        info = promote(
            paths["course"], paths["primary"], paths["secondary"],
            section=plan["section"], assignment=paths["assignment"],
            assignment_sha=plan["assignment_sha256"],
            campaign_id=plan["campaign_id"], code_sha=plan["code_commit"],
            authorization=authorization,
        )
        details = {"status": info["state"],
                   "pdf_sha256": manifest["candidate_pdf_sha256"],
                   "mp4_sha256": manifest["candidate_mp4_sha256"],
                   "receipt_sha256": manifest["candidate_receipt_sha256"]}
    elif phase == "recover-promote":
        # Resumes a crash AFTER source replacement but BEFORE stage evidence
        # was saved. Never reruns promote() or rewrites production files.
        package_receipt = paths["primary"] / "promotion_pending_independent_audit.json"
        receipt = json.loads(package_receipt.read_text(encoding="utf-8"))
        if receipt.get("state") != "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION":
            raise CoordinationError("Cannot recover: no verified owner transaction record")
        manifest = json.loads((paths["secondary"] / "package_manifest.json").read_text(encoding="utf-8"))
        pins = manifest_pins(manifest)
        if (receipt["pdf_sha256"] != pins["expected_pdf_sha256"]
            or receipt["mp4_sha256"] != pins["expected_mp4_sha256"]
            or receipt["receipt_sha256"] != pins["expected_receipt_sha256"]):
            raise CoordinationError("Cannot recover: original promotion record differs")
        check = destination_audit(paths["course"], paths["secondary"], **pins)
        owner.assert_held()
        details = {"status": "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION",
                   "pdf_sha256": check["corrected_pdf_sha256"],
                   "mp4_sha256": check["corrected_mp4_sha256"],
                   "receipt_sha256": check["receipt_sha256"]}
        # Also repair missing standard promote journal entry, but only after
        # exact validation of the existing (already replaced) production files.
        save_once(record_path(paths, "promote", host),
                  evidence(plan, paths, "promote", host, plan_sha, details))
    elif phase == "audit-destination":
        owner_receipt = verified_record(plan, paths, "promote",
                                        owner_name_from_assignment(plan, paths), plan_sha)
        if owner_receipt["status"] != "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION":
            raise CoordinationError("No matching completed owner transaction")
        manifest = json.loads((paths["secondary"] / "package_manifest.json").read_text(encoding="utf-8"))
        pins = manifest_pins(manifest)
        if replication_wait:
            await_expected_replica(paths["course"], paths["secondary"],
                                   timeout_seconds=replication_wait, **pins)
        check = destination_audit(paths["course"], paths["secondary"], **pins)
        details = {"status": check["state"],
                   "inventory_sha256": check["backup_inventory_sha256"],
                   "pdf_sha256": check["corrected_pdf_sha256"],
                   "mp4_sha256": check["corrected_mp4_sha256"],
                   "receipt_sha256": check["receipt_sha256"]}
    else:  # complete: status only, never writes a course completion or Moodle item
        manifest = json.loads((paths["secondary"] / "package_manifest.json").read_text(encoding="utf-8"))
        pins = manifest_pins(manifest)
        for reviewer in plan["reviewers"]:
            old = verified_record(plan, paths, "audit-destination", reviewer, plan_sha)
            if (old["status"] != "INDEPENDENT_DESTINATION_TECHNICAL_AUDIT_PASS"
                or old["inventory_sha256"] != manifest["original_inventory_sha256"]
                or old["pdf_sha256"] != pins["expected_pdf_sha256"]
                or old["mp4_sha256"] != pins["expected_mp4_sha256"]
                or old["receipt_sha256"] != pins["expected_receipt_sha256"]):
                raise CoordinationError("Independent destination evidence does not match source-bound package")
        destination_audit(paths["course"], paths["secondary"], **pins)
        details = {"status": "TWO_INDEPENDENT_DESTINATION_AUDITS_PASS_NOT_MOODLE_PUBLISHED"}
    record = evidence(plan, paths, phase, host, plan_sha, details)
    save_once(record_path(paths, phase, host), record)
    return record


def owner_name_from_assignment(plan: dict, paths: dict[str, Path]) -> str:
    raw = paths["assignment"].read_bytes()
    if hashlib.sha256(raw).hexdigest() != plan["assignment_sha256"]:
        raise CoordinationError("Assignment was modified during verification")
    return json.loads(raw.decode("utf-8"))["owners"][plan["section"]]


def status(plan: dict, paths: dict[str, Path], plan_sha: str) -> dict:
    owner = owner_name_from_assignment(plan, paths)
    output = {"section": plan["section"], "owner": owner, "reviewers": plan["reviewers"],
              "plan_sha256": plan_sha, "phases": {},
              "production_publication_automated": False}
    for phase in PHASES[:-1]:
        identities = plan["reviewers"] if phase in ("audit-backup", "audit-destination") else [owner]
        if phase == "complete":
            identities = [owner]
        output["phases"][phase] = {}
        for identity in identities:
            file = record_path(paths, phase, identity)
            if file.exists():
                try:
                    detail = verified_record(plan, paths, phase, identity, plan_sha)
                    output["phases"][phase][identity] = detail["status"]
                except (ValueError, OSError, KeyError, CoordinationError):
                    output["phases"][phase][identity] = "INVALID_OR_STALE_EVIDENCE"
            else:
                output["phases"][phase][identity] = "PENDING"
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--replication-wait-seconds", type=float, default=0)
    p.add_argument("--authorization", default="")
    opts = p.parse_args()
    if not 0 <= opts.replication_wait_seconds <= 300:
        p.error("Replication timeout must be in [0,300]")
    if opts.phase != "audit-destination" and opts.replication_wait_seconds:
        p.error("Replication wait only applies to independent destination audits")
    if opts.phase != "promote" and opts.authorization:
        p.error("Production authorization only valid for promote phase")
    plan = pinned_plan(opts.plan, opts.plan_sha256)
    paths = locations(plan)
    if opts.phase == "status":
        response = execute(plan, paths, opts.plan_sha256, opts.phase)
    else:
        # Exclusive local execution per approved PC: no phase overlaps and
        # interrupted locks require manual owner/process inspection.
        workspace = local_path(
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "MicroGen_ReleaseCoordinator_Locks" / plan["package_tag"],
            "Coordinator lock directory")
        workspace.mkdir(parents=True, exist_ok=True)
        with LocalExclusiveRun(workspace):
            response = execute(
                plan, paths, opts.plan_sha256, opts.phase,
                authorization=opts.authorization,
                replication_wait=opts.replication_wait_seconds)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
