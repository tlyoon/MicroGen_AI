#!/usr/bin/env python3
"""Read-only release-readiness inspection of legacy MicroGen_AI MP4 candidates.

A successful MP4 candidate is NOT a complete publishable lecture bundle. This
module has no promotion, overwrite, Moodle, or completion-receipt writer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import microgen_quality as quality
from microgen_legacy_video_repair import inspect_source_timing_provenance
from microgen_legacy_video_batch import BatchError, validate_completed


class ReleaseGateError(RuntimeError):
    pass


KNOWN_NARRATION_REPAIRS = {"5.6", "7.2"}


def inspect_release(source: Path, corrected_pdf: Path, video_dir: Path,
                    *, expected_pdf_sha256: str, section: str) -> dict:
    source = Path(source).resolve()
    corrected_pdf = Path(corrected_pdf).resolve()
    video_dir = Path(video_dir).resolve()
    outcome = {
        "section": section, "status": "BLOCKED",
        "may_publish": False, "completion_receipt_created": False,
        "academic_review_signed_by_tool": False,
        "reasons": [], "advisories": [],
    }
    reasons = outcome["reasons"]
    advisories = outcome["advisories"]
    if section != source.name:
        reasons.append("Source folder does not match requested section")
        return outcome
    if section in KNOWN_NARRATION_REPAIRS:
        reasons.append("Known truncated spoken narration title requires audio correction")
    if not corrected_pdf.is_file() or quality.sha256(corrected_pdf) != expected_pdf_sha256:
        reasons.append("Corrected PDF does not match pinned SHA256")
        return outcome
    try:
        pdf_check = quality.check_slide_pdf(corrected_pdf, require_footer=True)
        pages = pdf_check["pages"]
        outcome["slide_count"] = pages
    except Exception as exc:
        reasons.append(f"Corrected PDF failed strict validation: {exc}")
        return outcome
    try:
        # SHA of original source media, candidate MP4, and decoded AAC packets
        # are checked again; do NOT trust only an existing JSON success label.
        record = validate_completed(
            video_dir, expected_pdf_sha=expected_pdf_sha256, source=source
        )
        outcome["candidate_mp4_sha256"] = record["corrected_mp4_sha256"]
        verification = record["candidate_video_verification"]
        scenes = verification["corrected_scene_validation"]
        shifts = verification["scene_timing_error_seconds"]
        if len(scenes) != pages or len(record["visual_scene_validation"]) != pages:
            reasons.append("Source/candidate scene counts differ from corrected slides")
        if len(shifts) != pages - 1:
            reasons.append("Scene transition count is inconsistent")
        if any(abs(float(x)) > 0.4 for x in shifts):
            reasons.append("Scene timing drift is excessive")
        if any(float(x["expected_mean_absolute_pixel_difference"]) > 11.0
               for x in scenes):
            reasons.append("Pixel deviation is excessive")
    except (BatchError, OSError, ValueError, TypeError, KeyError) as exc:
        reasons.append(f"Candidate MP4 failed video hash or stream checks: {exc}")
    try:
        provenance = inspect_source_timing_provenance(source, pages)
        outcome["source_provenance"] = provenance
        if not provenance.get("narration_sidecar_sha256"):
            reasons.append("Missing slide-aligned narration sidecar: manual provenance decision required")
        if provenance["wav_files_present"] == 0:
            advisories.append(
                "Per-slide WAVs absent; original AAC is independently preserved, "
                "but future audio regeneration requires voice/provider provenance"
            )
    except Exception as exc:
        reasons.append(f"Narration/WAV provenance is inconsistent: {exc}")
    if not reasons:
        outcome["status"] = "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW"
        # Always false: operator must separately backup, create a valid
        # source-bound completion receipt, and perform destination QA.
    return outcome


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--corrected-pdf", type=Path, required=True)
    p.add_argument("--video-dir", type=Path, required=True)
    p.add_argument("--section", required=True)
    p.add_argument("--expected-pdf-sha256", required=True)
    args = p.parse_args()
    result = inspect_release(
        args.source, args.corrected_pdf, args.video_dir,
        expected_pdf_sha256=args.expected_pdf_sha256,
        section=args.section
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
