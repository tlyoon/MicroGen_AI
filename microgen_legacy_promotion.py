#!/usr/bin/env python3
"""Backup-first legacy visual promotion, separate from standard WAV-based v1 receipts.

By default only PREPARES an isolated local review package. Production replacement
requires explicit opt-in, an immutable Drive owner, two verified full backups,
and remains pending independent second-PC destination acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
from pathlib import Path

import microgen_quality as quality
from microgen_drive_assignments import DriveAssignedOwner
from microgen_legacy_release_gate import inspect_release
from microgen_legacy_video_batch import LocalExclusiveRun, verify_code, local_path

MARKER = ".microgen_legacy_visual_repair_receipt.json"
EVIDENCE = ".microgen_legacy_video_evidence.json"
REQUIRED = ("source.pdf", "slides.tex", "script.txt", "script_tts.json",
            "slides.pdf", "slides.mp4")


class PromotionError(RuntimeError):
    pass


def encoded(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise PromotionError("Course source directory missing")
    found = {}
    for p in root.rglob("*"):
        if p.is_symlink():
            raise PromotionError("Symlink in source bundle")
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel.casefold() in {name.casefold() for name in found}:
                raise PromotionError("Case-insensitive filename collision")
            found[rel] = quality.sha256(p)
    if not set(REQUIRED).issubset(found):
        raise PromotionError("Source lecture bundle incomplete")
    if MARKER in found or ".microgen_verified_completion.json" in found:
        raise PromotionError("Already receipt-bound production requires separate migration")
    return dict(sorted(found.items()))


def snapshot(source: Path, copy: Path, expected: dict[str, str]):
    if copy.exists():
        raise PromotionError("Backup exists, never overwrite")
    copy.mkdir(parents=True)
    for rel, digest in expected.items():
        dest = copy / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dest)
        if quality.sha256(dest) != digest:
            raise PromotionError(f"Snapshot checksum mismatch: {rel}")


def verify_snapshot(root: Path, expected: dict[str, str]):
    all_files = {p.relative_to(root).as_posix(): quality.sha256(p)
                 for p in root.rglob("*") if p.is_file()}
    if all_files != expected:
        raise PromotionError("Backup snapshot invalid or altered")


def receipt_for(source: Path, pdf: Path, video: Path, result: dict,
                assumed_approval: bool) -> dict:
    original = {name: quality.sha256(source / name) for name in REQUIRED}
    figure_hashes = quality.canonical_figure_hashes(
        quality.check_graphics(source / "slides.tex"))
    return {
        "schema_version": 2,
        "kind": "legacy_visual_audio_preservation_v2",
        "validation": "unchanged AAC + verified original/corrected visual scenes; not new TTS or scientific signoff",
        "source_file_sha256_before_repair": original,
        "figure_sha256": figure_hashes,
        "corrected_pdf_sha256": quality.sha256(pdf),
        "corrected_mp4_sha256": quality.sha256(video),
        "aac_sha256": result["original_audio_sha256"],
        "source_video_report_sha256": hashlib.sha256(encoded(result)).hexdigest(),
        "scene_count": len(result["candidate_video_verification"]["corrected_scene_validation"]),
        "wav_status": "not_retained_not_regenerated",
        "academic_approval_assumed_at_user_direction": assumed_approval,
        "human_signed_review_created": False,
        "moodle_published": False,
    }


def legacy_receipt_valid(dest: Path) -> bool:
    """Hash-bind corrected legacy output; not interchangeable with v1 completion."""
    try:
        doc = json.loads((dest / MARKER).read_text(encoding="utf-8-sig"))
        if doc["schema_version"] != 2 or doc["kind"] != "legacy_visual_audio_preservation_v2":
            return False
        for name, digest in doc["source_file_sha256_before_repair"].items():
            if name not in ("slides.pdf", "slides.mp4") and quality.sha256(dest / name) != digest:
                return False
        for name, digest in doc["figure_sha256"].items():
            if quality.sha256(dest / name) != digest:
                return False
        if quality.sha256(dest / "slides.pdf") != doc["corrected_pdf_sha256"]:
            return False
        if quality.sha256(dest / "slides.mp4") != doc["corrected_mp4_sha256"]:
            return False
        evidence_file = dest / EVIDENCE
        if quality.sha256(evidence_file) != doc["source_video_report_sha256"]:
            return False
        report = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
        if report["status"] != "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED":
            return False
        if report["corrected_mp4_sha256"] != doc["corrected_mp4_sha256"]:
            return False
        if report["old_media_sha256"]["old_mp4"] != doc["source_file_sha256_before_repair"]["slides.mp4"]:
            return False
        if report["old_media_sha256"]["old_pdf"] != doc["source_file_sha256_before_repair"]["slides.pdf"]:
            return False
        if report["original_audio_sha256"] != doc["aac_sha256"] or report["candidate_audio_sha256"] != doc["aac_sha256"]:
            return False
        scenes = report["candidate_video_verification"]["corrected_scene_validation"]
        shifts = report["candidate_video_verification"]["scene_timing_error_seconds"]
        if len(scenes) != doc["scene_count"] or len(shifts) != doc["scene_count"] - 1:
            return False
        if any(abs(float(s)) > 0.4 for s in shifts):
            return False
        if any(float(s["expected_mean_absolute_pixel_difference"]) > 11.0 for s in scenes):
            return False
        from microgen_legacy_video_repair import audio_stream_hash
        if audio_stream_hash(dest / "slides.mp4") != doc["aac_sha256"]:
            return False
        quality.check_slide_pdf(dest / "slides.pdf", require_footer=True)
        return type(doc["scene_count"]) is int and doc["scene_count"] > 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return False


def prepare(course: Path, candidate: Path, package: Path, *,
            section: str, expected_pdf_sha: str, academic_assumed: bool = True):
    course, candidate, package = (Path(x).resolve() for x in (course, candidate, package))
    local_path(package, "Review package")
    if package.exists() or package in course.parents or course in package.parents:
        raise PromotionError("Review package exists or overlaps the course")
    if course.name != section or not re.fullmatch(r"\d+\.\d+", section):
        raise PromotionError("Requested section/source mismatch")
    source_hashes = inventory(course)
    pdf = candidate / "corrected_slides.pdf"
    video = candidate / "corrected_slides.mp4"
    gate = inspect_release(course, pdf, candidate,
                           expected_pdf_sha256=expected_pdf_sha, section=section)
    if gate["status"] != "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW":
        raise PromotionError("Release gate blocked: " + "; ".join(gate["reasons"]))
    report = json.loads((candidate / "video_repair_report.json").read_text(encoding="utf-8-sig"))
    package.mkdir(parents=True)
    try:
        snapshot(course, package / "original", source_hashes)
        verify_snapshot(package / "original", source_hashes)
        output = package / "candidate"
        output.mkdir()
        for source, name in ((pdf, "slides.pdf"), (video, "slides.mp4")):
            shutil.copy2(source, output / name)
            if quality.sha256(source) != quality.sha256(output / name):
                raise PromotionError(f"Candidate copied incorrectly: {name}")
        (output / "video_repair_report.json").write_bytes(encoded(report))
        (output / EVIDENCE).write_bytes(encoded(report))
        receipt = receipt_for(course, pdf, video, report, academic_assumed)
        (output / MARKER).write_bytes(encoded(receipt))
        if inventory(course) != source_hashes:
            raise PromotionError("Source changed during backup")
        manifest = {
            "schema_version": 1,
            "state": "PREPARED_NOT_PUBLISHED",
            "course": str(course), "section": section,
            "original_files": source_hashes,
            "original_inventory_sha256": hashlib.sha256(encoded(source_hashes)).hexdigest(),
            "candidate_pdf_sha256": quality.sha256(output / "slides.pdf"),
            "candidate_mp4_sha256": quality.sha256(output / "slides.mp4"),
            "candidate_receipt_sha256": quality.sha256(output / MARKER),
            "candidate_evidence_sha256": quality.sha256(output / EVIDENCE),
            "publication_allowed": False,
        }
        (package / "package_manifest.json").write_bytes(encoded(manifest))
        return manifest
    except BaseException:
        (package / "FAILED_PREPARATION.txt").write_text(
            "Not suitable for promotion. Preserve for investigation.\n", encoding="utf-8")
        raise


def verify_package(package: Path, course: Path):
    m = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    if m["state"] != "PREPARED_NOT_PUBLISHED" or Path(m["course"]).resolve() != course.resolve():
        raise PromotionError("Incorrect package/destination")
    if hashlib.sha256(encoded(m["original_files"])).hexdigest() != m["original_inventory_sha256"]:
        raise PromotionError("Original inventory tampered")
    verify_snapshot(package / "original", m["original_files"])
    if inventory(course) != m["original_files"]:
        raise PromotionError("Course changed after backup")
    cand = package / "candidate"
    for name, key in (("slides.pdf", "candidate_pdf_sha256"),
                      ("slides.mp4", "candidate_mp4_sha256"),
                      (MARKER, "candidate_receipt_sha256"),
                      (EVIDENCE, "candidate_evidence_sha256")):
        if quality.sha256(cand / name) != m[key]:
            raise PromotionError(f"Staged candidate changed: {name}")
    return m


def promote(course: Path, package: Path, second_backup: Path, *,
            section: str, assignment: Path, assignment_sha: str, campaign_id: str,
            code_sha: str, authorization: str):
    if authorization != "AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT":
        raise PromotionError("Explicit single-bundle production authorization required")
    course, package, second_backup = (Path(x).resolve() for x in (course, package, second_backup))
    local_path(package, "Promotion package")
    verify_code(Path(__file__).resolve().parent, code_sha)
    if course.name != section:
        raise PromotionError("Section mismatch")
    owner = DriveAssignedOwner(assignment, assignment_sha, campaign_id,
                               course.parent.parent, section)
    owner.assert_held()
    with LocalExclusiveRun(package):
        m = verify_package(package, course)
        if package == second_backup or package in second_backup.parents:
            raise PromotionError("Independent backup overlaps original package")
        verify_snapshot(second_backup / "original", m["original_files"])
        owner.assert_held()
        replacements = ("slides.pdf", "slides.mp4", EVIDENCE, MARKER)
        pending = {}
        changed = []
        token = os.urandom(8).hex()
        try:
            # Recheck all original content before writing pending files.
            if inventory(course) != m["original_files"]:
                raise PromotionError("Source drift before promotion")
            for name in replacements:
                target = course / (name + ".microgen-" + token + ".candidate")
                shutil.copy2(package / "candidate" / name, target)
                if quality.sha256(target) != quality.sha256(package / "candidate" / name):
                    raise PromotionError("Destination staging checksum failed")
                pending[name] = target
            for name, expected in m["original_files"].items():
                if quality.sha256(course / name) != expected:
                    raise PromotionError("Source changed while staging")
            staged_names = {file.relative_to(course).as_posix()
                            for file in pending.values()}
            actual_names = {file.relative_to(course).as_posix()
                            for file in course.rglob("*") if file.is_file()}
            if actual_names != set(m["original_files"]) | staged_names:
                raise PromotionError("Unrelated course files added or removed during staging")
            for name in replacements:
                owner.assert_held()
                os.replace(pending[name], course / name)
                changed.append(name)
            if not legacy_receipt_valid(course):
                raise PromotionError("New legacy visual receipt invalid")
            for name, expected in m["original_files"].items():
                if name not in ("slides.pdf", "slides.mp4") and quality.sha256(course / name) != expected:
                    raise PromotionError("Unrelated original file changed")
        except BaseException as original_error:
            try:
                for name in reversed(changed):
                    previous = package / "original" / name
                    if previous.exists():
                        shutil.copy2(previous, course / name)
                    else:
                        (course / name).unlink(missing_ok=True)
                for tmp in pending.values():
                    tmp.unlink(missing_ok=True)
                if inventory(course) != m["original_files"]:
                    raise PromotionError("Rollback did not restore original inventory")
            except BaseException as rollback_error:
                (package / "CRITICAL_ROLLBACK_FAILED.txt").write_text(
                    str(original_error) + "\n" + str(rollback_error), encoding="utf-8")
                raise PromotionError("CRITICAL rollback failure; manual recovery required") from rollback_error
            raise
        finally:
            for tmp in pending.values():
                tmp.unlink(missing_ok=True)
        report = {
            "state": "PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION",
            "section": section, "backup_manifest_sha256": m["original_inventory_sha256"],
            "pdf_sha256": m["candidate_pdf_sha256"],
            "mp4_sha256": m["candidate_mp4_sha256"],
            "receipt_sha256": m["candidate_receipt_sha256"],
            "evidence_sha256": m["candidate_evidence_sha256"],
            "operator_host": socket.gethostname(), "moodle_published": False,
        }
        (package / "promotion_pending_independent_audit.json").write_bytes(encoded(report))
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--course", required=True, type=Path)
    p.add_argument("--section", required=True)
    p.add_argument("--package", required=True, type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--pdf-sha256")
    p.add_argument("--promote", action="store_true")
    p.add_argument("--second-backup", type=Path)
    p.add_argument("--assignment", type=Path)
    p.add_argument("--assignment-sha256")
    p.add_argument("--campaign-id")
    p.add_argument("--code-sha")
    p.add_argument("--authorization")
    a = p.parse_args()
    if not a.promote:
        if not a.candidate or not a.pdf_sha256:
            p.error("Preparation requires --candidate and --pdf-sha256")
        result = prepare(a.course, a.candidate, a.package,
                         section=a.section, expected_pdf_sha=a.pdf_sha256)
    else:
        needed = ("second_backup", "assignment", "assignment_sha256",
                  "campaign_id", "code_sha", "authorization")
        if any(not getattr(a, field) for field in needed):
            p.error("Promotion requires explicit owner, code and second-backup authorization")
        result = promote(a.course, a.package, a.second_backup,
                         section=a.section, assignment=a.assignment,
                         assignment_sha=a.assignment_sha256,
                         campaign_id=a.campaign_id, code_sha=a.code_sha,
                         authorization=a.authorization)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
