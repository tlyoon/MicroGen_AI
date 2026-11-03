"""Atomic private chapter handoff from independently verified source-bound lessons.

Combines the existing source/scientific campaign with exact slide/narration
identity checks and provider-neutral voice requests. No text generation,
TTS synthesis, model installation, provider call, billing or publication.
PRIVATE voice files deliberately contain the original authored narration.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from microgen_portable_private_authoring_gate import _safe_output
from microgen_pronunciation_closed_loop import sha_file
from microgen_private_unified_campaign import audit_unified_private_campaign
from microgen_portable_voice_input_handoff import (
    prepare_portable_voice_input_handoff,
)
from microgen_portable_audio_import import make_audio_capture_template


class PrivateChapterCampaignError(ValueError):
    pass


def _private_root(path: Path) -> Path:
    value = Path(path)
    if value.is_symlink() or not value.is_dir():
        raise PrivateChapterCampaignError("Real private stage or slides directory required")
    real = value.resolve(strict=True)
    if any(str(x).casefold() == "my drive" for x in real.parts):
        raise PrivateChapterCampaignError("Private stage and slides cannot be in cloud-synced My Drive")
    return real


def _source_input_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 15_000_000:
        raise PrivateChapterCampaignError("Original private source/receipt input missing or unsafe")
    return sha_file(path)


def audit_private_chapter_handoff(manifest: dict, output: Path) -> dict:
    """Publish one complete chapter preproduction bundle or nothing.

    Explicit expected_sections prevents accidental omission of a subsection.
    Per-section source, authored response, source-grounded stage and rendered
    slide evidence are independently checked with existing proven verifiers.
    """
    if not isinstance(manifest, dict) or set(manifest) != {
        "chapter_id", "expected_sections", "cases"
    }:
        raise PrivateChapterCampaignError("Explicit chapter, full expected inventory and cases required")
    chapter = manifest["chapter_id"]
    expected = manifest["expected_sections"]
    cases = manifest["cases"]
    if (not isinstance(chapter, str) or not re.fullmatch(r"[1-9][0-9]?", chapter)
        or not isinstance(expected, list) or not 2 <= len(expected) <= 12
        or not isinstance(cases, list) or len(cases) != len(expected)):
        raise PrivateChapterCampaignError("Expected 2–12 declared chapter sections")
    required = [f"{chapter}.{i}" for i in range(1, len(expected)+1)]
    if expected != required:
        raise PrivateChapterCampaignError("Section inventory must be contiguous, explicit and complete")
    coverage_cases = []
    checked = []
    frozen = {}
    guarded_dirs = []
    for case, section in zip(cases, required):
        if (not isinstance(case, dict) or set(case) != {
            "section_id", "source_pdf", "private_packet", "private_draft",
            "stage", "slides"} or case["section_id"] != section):
            raise PrivateChapterCampaignError("Unexpected, missing or reordered chapter section")
        stage = _private_root(Path(case["stage"]))
        slides = _private_root(Path(case["slides"]))
        if slides == stage or slides in stage.parents or stage in slides.parents:
            raise PrivateChapterCampaignError("Source stage and rendered slides must be separate")
        guarded_dirs.extend((stage, slides))
        original = Path(case["source_pdf"])
        protected = [original, Path(case["private_packet"]),
            Path(case["private_draft"]),
            *(stage / name for name in ("source.pdf", "contract.json",
                                      "narration.json", "plan.json")),
            *(slides / name for name in ("slides_teaching_candidate.pdf",
                                        "teaching_slide_receipt.json"))]
        # Protect exact image files, including source-aligned original crops.
        try:
            contract = json.loads((stage/"contract.json").read_text(encoding="utf8"))
            figures = contract.get("figures", [])
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise PrivateChapterCampaignError("Malformed private stage figure inventory") from exc
        if not isinstance(figures, list) or len(figures) > 60:
            raise PrivateChapterCampaignError("Unsafe source figure inventory")
        for row in figures:
            if not isinstance(row, dict) or not isinstance(row.get("filename"), str):
                raise PrivateChapterCampaignError("Malformed source figure identifier")
            name = row["filename"]
            if name in ("", ".", "..") or Path(name).name != name or "/" in name or "\\" in name:
                raise PrivateChapterCampaignError("Nested or unsafe private source figure")
            protected.append(stage/name)
        for path in protected:
            key = path.resolve(strict=False)
            value = _source_input_digest(path)
            if key in frozen and frozen[key] != value:
                raise PrivateChapterCampaignError("Protected input altered across chapter cases")
            frozen[key] = value
        if frozen[original.resolve(strict=True)] != frozen[(stage/"source.pdf").resolve(strict=True)]:
            raise PrivateChapterCampaignError("Private stage differs from immutable original section")
        voice = prepare_portable_voice_input_handoff(stage, slides)
        if (voice.get("section_id") != section or
            voice.get("source_pdf_sha256") != frozen[original.resolve(strict=True)] or
            voice.get("formal_voice_synthesis_authorized") is not False or
            voice.get("publication_allowed") is not False or
            voice.get("provider_calls") != 0 or voice.get("local_model_invocations") != 0):
            raise PrivateChapterCampaignError("Voice candidate identity or nonpublication policy mismatch")
        checked.append((section, voice))
        coverage_cases.append({name: case[name] for name in (
            "section_id", "source_pdf", "private_packet", "private_draft", "stage")})
    dest = _safe_output(Path(output), Path(cases[0]["source_pdf"]))
    for protected in [*guarded_dirs, *frozen.keys()]:
        if dest == protected or dest in protected.parents or protected in dest.parents:
            raise PrivateChapterCampaignError("Chapter report cannot overlap source or media inputs")
    temp = Path(tempfile.mkdtemp(prefix=".microgen-chapter-private-", dir=dest.parent))
    try:
        combined = audit_unified_private_campaign(coverage_cases, temp/"source_science")
        by_section = {row["section_id"]: row for row in combined["sections"]}
        if set(by_section) != set(required):
            raise PrivateChapterCampaignError("Source/science chapter inventory does not match voice chapter")
        (temp/"voice_inputs").mkdir()
        (temp/"capture_templates").mkdir()
        rows = []
        for section, voice in checked:
            source_row = by_section[section]
            if (voice["source_pdf_sha256"] != source_row["original_source_sha256"] or
                voice["slide_count"] != source_row["authored_topics_verified"]):
                raise PrivateChapterCampaignError("Voice deck and original source/science receipt disagree")
            name = "section_" + section.replace(".", "_")
            request_file = temp/"voice_inputs"/f"{name}.json"
            request_file.write_text(json.dumps(voice, indent=2), encoding="utf8")
            capture = make_audio_capture_template(request_file)
            if (capture.get("formal_production_authorized") is not False or
                capture.get("declared_provider") is not None or
                capture.get("declared_voice") is not None):
                raise PrivateChapterCampaignError("External voice capture is not yet authorized")
            capture_file = temp/"capture_templates"/f"{name}_blank.json"
            capture_file.write_text(json.dumps(capture, indent=2), encoding="utf8")
            rows.append({
                "section_id": section,
                "original_source_sha256": source_row["original_source_sha256"],
                "source_passages_discovered": source_row["source_passages_discovered"],
                "source_passages_linked": source_row["source_passages_linked"],
                "high_interest_uncited_advisory": source_row["high_interest_uncited_advisory"],
                "authored_topics_and_slides_verified": voice["slide_count"],
                "original_author_draft_and_compiled_text_identity_verified":source_row[
                    "original_source_draft_and_compiled_spoken_visual_text_identical"],
                "historical_authoring_sha_lineage_discrepancy_advisory":source_row[
                    "historical_authoring_sha_lineage_discrepancy_advisory"],
                "rendered_pdf_sha256": voice["rendered_pdf_sha256"],
                "narration_sha256": voice["narration_sha256"],
                "voice_request_file": f"voice_inputs/{name}.json",
                "voice_request_sha256": sha_file(request_file),
                "empty_capture_template_file": f"capture_templates/{name}_blank.json",
                "capture_template_sha256": sha_file(capture_file),
                "formal_voice_audio_generated": False,
                "source_and_voice_fully_published": False,
            })
        if len(rows) != len(required) or any(sha_file(p) != h for p, h in frozen.items()):
            raise PrivateChapterCampaignError("Protected source/slide inputs changed during campaign")
        report = {
            "schema_version": 1,
            "status": "PRIVATE_COMPLETE_CHAPTER_SOURCE_AND_VOICE_HANDOFF_READY_NOT_PUBLISHED",
            "chapter_id": chapter,
            "section_count": len(rows),
            "total_source_passages_discovered": sum(x["source_passages_discovered"] for x in rows),
            "total_source_passages_linked": sum(x["source_passages_linked"] for x in rows),
            "total_teaching_slides": sum(x["authored_topics_and_slides_verified"] for x in rows),
            "total_voice_requests": sum(x["authored_topics_and_slides_verified"] for x in rows),
            "historical_authoring_sha_discrepancy_advisory_count":sum(
                x["historical_authoring_sha_lineage_discrepancy_advisory"] for x in rows),
            "publisher_actual_chapter_outline_completeness_proven": False,
            "combined_source_science_receipt_sha256": sha_file(
                temp/"source_science"/"unified_private_campaign_receipt.json"),
            "sections": rows,
            "unapproved_voice_handoff_has_private_narration_text": True,
            "original_textbook_source_modified": False,
            "pdf_slides_regenerated": False,
            "tts_audio_generated": False,
            "provider_calls": 0,
            "locally_installed_language_models_invoked": 0,
            "complete_academic_semantics_proven": False,
            "formal_voice_approved": False,
            "copyright_rights_verified": False,
            "publication_allowed": False,
        }
        (temp/"chapter_private_readiness_receipt.json").write_text(
            json.dumps(report, indent=2), encoding="utf8")
        if dest.exists() or dest.is_symlink():
            raise PrivateChapterCampaignError("Chapter output appeared before atomic completion")
        os.rename(temp, dest)
        return report
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--new-private-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (args.private_manifest.is_symlink() or
        not args.private_manifest.is_file() or
        args.private_manifest.stat().st_size > 250_000):
        raise PrivateChapterCampaignError("Bounded private chapter manifest required")
    manifest = json.loads(args.private_manifest.read_text(encoding="utf8"))
    result = audit_private_chapter_handoff(manifest, args.new_private_output)
    # Never print private source excerpts, user paths or author narration.
    print(json.dumps({
        "status": result["status"], "chapter": result["chapter_id"],
        "sections": result["section_count"],
        "slides_and_voice_requests": result["total_teaching_slides"],
        "provider_calls": 0, "publication_allowed": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
