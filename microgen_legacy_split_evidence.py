#!/usr/bin/env python3
"""Conservatively adapt split historical postrender verification to modern report.

Never mutates the legacy archive, production source files, or a preexisting
destination. Original and independent QA evidence remain preserved unchanged.
A successful adaptation creates a CANDIDATE only, never a completion receipt.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from microgen_legacy_video_repair import audio_stream_hash
from microgen_legacy_video_batch import validate_completed
from microgen_legacy_release_gate import inspect_release
from microgen_quality import check_slide_pdf, sha256


class EvidenceAdaptationError(RuntimeError):
    pass


def insist(ok: bool, reason: str) -> None:
    if not ok:
        raise EvidenceAdaptationError(reason)


def normalize(source: Path, old: Path, destination: Path) -> dict:
    source, old, destination = (Path(p).resolve() for p in (source, old, destination))
    insist(source.is_dir() and old.is_dir(), "Source and archived candidate must exist")
    insist(not destination.exists(), "Destination already exists; never overwrite")
    insist(not (destination == source or source in destination.parents
                or destination == old or old in destination.parents),
           "Output overlaps the production source or original archive")
    insist(not (destination in source.parents or destination in old.parents),
           "Output cannot replace a parent directory")
    legacy_report = old / "video_repair_report.json"
    historical_proof = old / "independent_postrender_verification.json"
    pdf, mp4 = old / "corrected_slides.pdf", old / "corrected_slides.mp4"
    report_bytes = legacy_report.read_bytes()
    proof_bytes = historical_proof.read_bytes()
    report = json.loads(report_bytes.decode("utf-8-sig"))
    proof = json.loads(proof_bytes.decode("utf-8-sig"))
    insist(report.get("status") == "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED",
           "Archived candidate did not pass historical QA")
    insist(proof.get("status") == "VERIFIED_ISOLATED_CANDIDATE_NOT_PUBLISHED",
           "Independent historical postrender proof did not pass")
    insist("candidate_video_verification" not in report,
           "Use the normal release gate for modern candidates; no adaptation")
    old_hashes = report["old_media_sha256"]
    mp4_hash = sha256(mp4)
    pdf_hash = sha256(pdf)
    insist(old_hashes["old_pdf"] == sha256(source / "slides.pdf")
           and old_hashes["old_mp4"] == sha256(source / "slides.mp4"),
           "Original source slide PDF or video has changed")
    insist(old_hashes["corrected_pdf"] == pdf_hash
           and proof["source_pdf_sha256"] == pdf_hash,
           "Corrected PDF hash differs between evidence sources")
    insist(report["corrected_mp4_sha256"] == mp4_hash
           and proof["candidate_mp4_sha256"] == mp4_hash,
           "Corrected MP4 is not identical to independently validated candidate")
    old_audio = audio_stream_hash(source / "slides.mp4")
    new_audio = audio_stream_hash(mp4)
    insist(old_audio == new_audio == report["original_audio_sha256"]
           == report["candidate_audio_sha256"]
           == proof["original_audio_sha256"] == proof["candidate_audio_sha256"]
           and proof["same_audio_packets"] is True,
           "Actual encoded audio does not match the historic audio-preservation proof")
    pages = check_slide_pdf(pdf, require_footer=True)["pages"]
    before = report["visual_scene_validation"]
    after = proof["corrected_scene_validation"]
    shifts = proof["scene_timing_error_seconds"]
    boundaries = proof["candidate_boundaries_seconds"]
    insist(len(before) == len(after) == pages and len(shifts) == len(boundaries) == pages - 1,
           "Mismatch between slide pages, before/after scene counts or transitions")
    insist(boundaries == report["video_slide_boundaries_seconds"],
           "Independent postrender transition timestamps differ from original")
    insist(float(proof["corrected_video_seconds"]) > 0
           and abs(float(proof["corrected_video_seconds"]) - float(report["candidate_seconds"])) < 0.35,
           "Video duration differs from historical receipt")
    insist(all(isinstance(x, (int, float)) and abs(x) <= .4 for x in shifts),
           "Pixel-scene transition drift exceeds gate tolerance")
    insist(all(isinstance(s, dict) and s.get("scene") == i
               and s.get("matching_pdf_page") == i
               and float(s["expected_mean_absolute_pixel_difference"]) <= 11.0
               for i, s in enumerate(after, 1)),
           "Independent candidate scene-to-slide pixel proof invalid")
    insist(all(isinstance(s, dict) and s.get("scene") == i
               and s.get("matching_pdf_page") == i
               for i, s in enumerate(before, 1)),
           "Original video scene-to-slide proof invalid")
    adapted = dict(report)
    adapted["candidate_video_verification"] = dict(proof)
    adapted["historical_split_evidence_provenance"] = {
        "original_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "independent_postrender_proof_sha256": hashlib.sha256(proof_bytes).hexdigest(),
        "original_candidate_mp4_sha256": mp4_hash,
        "original_candidate_pdf_sha256": pdf_hash,
        "files_reencoded": False,
        "academic_signoff_created": False,
        "production_published": False,
    }
    destination.mkdir(parents=True)
    try:
        for name, file in (("corrected_slides.pdf", pdf), ("corrected_slides.mp4", mp4),
                           ("original_video_repair_report.json", legacy_report),
                           ("independent_postrender_verification.json", historical_proof)):
            shutil.copy2(file, destination / name)
            insist(sha256(file) == sha256(destination / name), "Copy altered " + name)
        (destination / "video_repair_report.json").write_text(
            json.dumps(adapted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        validate_completed(destination, expected_pdf_sha=pdf_hash, source=source)
        verdict = inspect_release(source, destination / "corrected_slides.pdf",
                                  destination, expected_pdf_sha256=pdf_hash, section=source.name)
        insist(verdict["status"] == "TECHNICAL_CANDIDATE_READY_FOR_OPERATOR_RELEASE_REVIEW",
               "Modern release gate rejected adapted candidate: " + repr(verdict["reasons"]))
        return {"status": "ADAPTED_CANDIDATE_PASSED_RELEASE_GATE_NOT_PUBLISHED",
                "source_section": source.name, "candidate_path": str(destination),
                "pdf_sha256": pdf_hash, "mp4_sha256": mp4_hash,
                "legacy_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                "independent_proof_sha256": hashlib.sha256(proof_bytes).hexdigest(),
                "scene_count": pages, "source_unmodified": True,
                "candidate_media_reencoded": False, "moodle_published": False}
    except BaseException:
        (destination / "FAILED_ADAPTATION_DO_NOT_PROMOTE.txt").write_text(
            "Inspection failed: preserve evidence and investigate; do not promote.\n",
            encoding="utf-8")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(normalize(options.source, options.archive, options.output),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
