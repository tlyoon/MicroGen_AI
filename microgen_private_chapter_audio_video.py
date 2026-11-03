"""All-or-nothing PRIVATE chapter WAV intake and optional offline video assembly.

Consumes PR267 chapter readiness evidence and PR265 externally captured WAVs.
No model, TTS synthesis, cloud, API, voice selection, permission grant or publishing.
WAV provenance, spoken words and narration rights remain unverified technically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from microgen_offline_diagnostic_av import build_demo_video
from microgen_portable_audio_import import (
    _verified_handoff, audit_portable_audio_import, make_audio_capture_template,
)
from microgen_portable_voice_input_handoff import _read_json
from microgen_pronunciation_closed_loop import sha_file


class PrivateChapterMediaError(ValueError):
    """Incomplete or unsafe private chapter audio/video evidence."""


def _private_directory(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise PrivateChapterMediaError("Real private directory required")
    root = path.resolve(strict=True)
    if any(part.casefold() == "my drive" for part in root.parts):
        raise PrivateChapterMediaError("Private media cannot use synced My Drive")
    return root


def _file(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 30_000_000:
        raise PrivateChapterMediaError("Missing or unsafe private input file")
    return path.resolve(strict=True)


def _frozen(frozen: dict, path: Path) -> str:
    path = _file(path)
    digest = sha_file(path)
    if path in frozen and frozen[path] != digest:
        raise PrivateChapterMediaError("Protected input changed")
    frozen[path] = digest
    return digest


def _chapter(chapter_bundle: Path, frozen: dict) -> tuple[dict, list]:
    root = _private_directory(chapter_bundle)
    receipt_path = root / "chapter_private_readiness_receipt.json"
    receipt = _read_json(_file(receipt_path))
    _frozen(frozen, receipt_path)
    chapter = receipt.get("chapter_id")
    sections = receipt.get("sections")
    if (receipt.get("status") !=
            "PRIVATE_COMPLETE_CHAPTER_SOURCE_AND_VOICE_HANDOFF_READY_NOT_PUBLISHED"
            or receipt.get("publication_allowed") is not False
            or not isinstance(chapter, str)
            or not re.fullmatch(r"[1-9][0-9]?", chapter)
            or not isinstance(sections, list) or not 2 <= len(sections) <= 12
            or receipt.get("section_count") != len(sections)
            or receipt.get("total_voice_requests") != receipt.get("total_teaching_slides")):
        raise PrivateChapterMediaError("Chapter readiness evidence invalid")
    expected = [f"{chapter}.{i}" for i in range(1, len(sections) + 1)]
    if [row.get("section_id") for row in sections] != expected:
        raise PrivateChapterMediaError("Chapter section inventory incomplete or unordered")
    shared = root / "source_science" / "unified_private_campaign_receipt.json"
    if _frozen(frozen, shared) != receipt.get("combined_source_science_receipt_sha256"):
        raise PrivateChapterMediaError("Chapter source/science campaign receipt drifted")
    verified = []
    for section, row in zip(expected, sections):
        name = "section_" + section.replace(".", "_")
        request_name = f"voice_inputs/{name}.json"
        template_name = f"capture_templates/{name}_blank.json"
        if (row.get("voice_request_file") != request_name
                or row.get("empty_capture_template_file") != template_name
                or row.get("original_author_draft_and_compiled_text_identity_verified")
                    is not True
                or row.get("authored_topics_and_slides_verified", 0) < 2):
            raise PrivateChapterMediaError("Chapter source/text lineage or safe filenames invalid")
        request_path = root / request_name
        template_path = root / template_name
        if (_frozen(frozen, request_path) != row.get("voice_request_sha256")
                or _frozen(frozen, template_path) != row.get("capture_template_sha256")):
            raise PrivateChapterMediaError("Voice request or capture template SHA drifted")
        handoff = _verified_handoff(request_path)
        template = _read_json(template_path)
        if (handoff.get("section_id") != section
                or handoff.get("slide_count") != row["authored_topics_and_slides_verified"]
                or handoff.get("source_pdf_sha256") != row.get("original_source_sha256")
                or handoff.get("rendered_pdf_sha256") != row.get("rendered_pdf_sha256")
                or handoff.get("narration_sha256") != row.get("narration_sha256")
                or template != make_audio_capture_template(request_path)):
            raise PrivateChapterMediaError("Original voice/text/template identity mismatch")
        verified.append((section, row, request_path))
    if sum(row["authored_topics_and_slides_verified"] for _, row, _ in verified) != (
            receipt.get("total_teaching_slides")):
        raise PrivateChapterMediaError("Chapter total slides disagree with sections")
    return receipt, verified


def make_chapter_capture_plan(chapter_bundle: Path, private_source_manifest: Path) -> dict:
    """Seed a PRIVATE editable plan; audio locations remain empty until supplied."""
    frozen = {}
    chapter, verified = _chapter(chapter_bundle, frozen)
    source_manifest = _read_json(_file(private_source_manifest))
    if (source_manifest.get("chapter_id") != chapter["chapter_id"]
            or source_manifest.get("expected_sections") != [
                section for section, _, _ in verified]
            or len(source_manifest.get("cases", [])) != len(verified)):
        raise PrivateChapterMediaError("Original private chapter inventory disagrees")
    cases = []
    for (section, row, _), case in zip(verified, source_manifest["cases"]):
        if case.get("section_id") != section:
            raise PrivateChapterMediaError("Original source/slide section order drifted")
        stage = _private_directory(Path(case["stage"]))
        slides = _private_directory(Path(case["slides"]))
        source = _file(Path(case["source_pdf"]))
        if (_frozen(frozen, source) != row["original_source_sha256"]
                or _frozen(frozen, stage / "narration.json") != row["narration_sha256"]
                or _frozen(frozen, slides / "slides_teaching_candidate.pdf") !=
                row["rendered_pdf_sha256"]):
            raise PrivateChapterMediaError("Current source/narration/deck no longer matches chapter")
        _frozen(frozen, slides / "teaching_slide_receipt.json")
        cases.append({
            "section_id": section,
            "source_pdf": str(source),
            "slides_dir": str(slides),
            "narration_qa": str(stage / "narration.json"),
            "audio_dir": None,
            "capture_manifest": None,
        })
    if any(sha_file(path) != value for path, value in frozen.items()):
        raise PrivateChapterMediaError("Original private input changed during planning")
    return {
        "schema_version": 1,
        "chapter_id": chapter["chapter_id"],
        "chapter_receipt_sha256": sha_file(
            _private_directory(chapter_bundle) / "chapter_private_readiness_receipt.json"),
        "sections": cases,
        "formal_voice_authorization_claimed": False,
        "publication_allowed": False,
    }


def _input_plan(plan_path: Path, chapter: dict, frozen: dict) -> list:
    plan = _read_json(_file(plan_path))
    _frozen(frozen, plan_path)
    if (set(plan) != {"schema_version", "chapter_id", "chapter_receipt_sha256",
                     "sections", "formal_voice_authorization_claimed", "publication_allowed"}
            or plan["schema_version"] != 1
            or plan["chapter_id"] != chapter["chapter_id"]
            or plan["chapter_receipt_sha256"] !=
            sha_file(_file(Path(chapter["_bundle"]) / "chapter_private_readiness_receipt.json"))
            or plan["formal_voice_authorization_claimed"] is not False
            or plan["publication_allowed"] is not False
            or not isinstance(plan["sections"], list)
            or len(plan["sections"]) != chapter["section_count"]):
        raise PrivateChapterMediaError("Chapter input plan or readiness SHA mismatch")
    return plan["sections"]


def _destination(output: Path, protected: set[Path]) -> Path:
    output = Path(output)
    target = output.resolve(strict=False)
    if (output.exists() or output.is_symlink() or not target.parent.is_dir()
            or any(p.casefold() == "my drive" for p in target.parts)):
        raise PrivateChapterMediaError("Fresh private output outside My Drive required")
    for path in protected:
        if target == path or target in path.parents or path in target.parents:
            raise PrivateChapterMediaError("Media output overlaps immutable private input")
    return target


def audit_chapter_captured_audio(
    chapter_bundle: Path, capture_plan: Path, new_output: Path, *,
    render_private_videos: bool = False, ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> dict:
    """Audit ALL section WAVs first; only then optionally create private MP4s."""
    frozen = {}
    bundle = _private_directory(chapter_bundle)
    receipt, expected = _chapter(bundle, frozen)
    chapter = dict(receipt, _bundle=str(bundle))
    cases = _input_plan(capture_plan, chapter, frozen)
    protected_dirs = {bundle}
    rows = []
    todo = []
    for case, (section, row, request_path) in zip(cases, expected):
        if not isinstance(case, dict) or set(case) != {
                "section_id", "source_pdf", "slides_dir", "narration_qa",
                "audio_dir", "capture_manifest"} or case["section_id"] != section:
            raise PrivateChapterMediaError("Missing or reordered audio/slide section input")
        if not all(isinstance(case[key], str) and case[key]
                   for key in ("source_pdf", "slides_dir", "narration_qa",
                               "audio_dir", "capture_manifest")):
            raise PrivateChapterMediaError("Chapter audio not yet supplied for every section")
        slides = _private_directory(Path(case["slides_dir"]))
        audio = _private_directory(Path(case["audio_dir"]))
        narration = _file(Path(case["narration_qa"]))
        capture = _file(Path(case["capture_manifest"]))
        protected_dirs.update((slides, audio, narration.parent))
        pdf = slides / "slides_teaching_candidate.pdf"
        slide_receipt = slides / "teaching_slide_receipt.json"
        if (_frozen(frozen, Path(case["source_pdf"])) != row["original_source_sha256"]
                or _frozen(frozen, pdf) != row["rendered_pdf_sha256"]
                or _frozen(frozen, narration) != row["narration_sha256"]):
            raise PrivateChapterMediaError("Original source, narration or deck differs from chapter proof")
        _frozen(frozen, slide_receipt)
        _frozen(frozen, capture)
        technical = audit_portable_audio_import(request_path, audio, capture)
        if (technical.get("section_id") != section
                or technical.get("source_pdf_sha256") != row["original_source_sha256"]
                or technical.get("rendered_pdf_sha256") != row["rendered_pdf_sha256"]
                or technical.get("slide_count") != row["authored_topics_and_slides_verified"]
                or technical.get("publication_allowed") is not False
                or technical.get("provider_calls") != 0
                or technical.get("local_model_invocations") != 0):
            raise PrivateChapterMediaError("External WAV acceptance is inconsistent with chapter")
        for item in technical["captured_wavs"]:
            if _frozen(frozen, audio / item["wav_filename"]) != item["wav_sha256"]:
                raise PrivateChapterMediaError("Source WAV modified during intake")
        rows.append({
            "section_id": section,
            "slide_count": technical["slide_count"],
            "original_source_pdf_sha256": row["original_source_sha256"],
            "rendered_pdf_sha256": row["rendered_pdf_sha256"],
            "narration_sha256": row["narration_sha256"],
            "voice_input_sha256": row["voice_request_sha256"],
            "capture_manifest_sha256": technical["capture_manifest_sha256"],
            "total_audio_seconds": round(sum(x["seconds"] for x in
                                             technical["captured_wavs"]), 3),
            "all_wav_hashes_and_pcm_verified": True,
            "declared_provider": technical["declared_provider"],
            "declared_voice": technical["declared_voice"],
            "provider_identity_independently_verified": False,
            "narration_words_actually_spoken_verified": False,
            "publication_allowed": False,
        })
        todo.append((section, slides, narration, audio, technical))
    output = _destination(new_output, protected_dirs | set(frozen))
    temp = Path(tempfile.mkdtemp(prefix=".microgen-chapter-av-", dir=output.parent))
    try:
        if render_private_videos:
            (temp / "section_videos").mkdir()
        for item, (section, slides, narration, audio, evidence) in zip(rows, todo):
            if render_private_videos:
                directory = temp / ("tmp_" + section.replace(".", "_"))
                video = build_demo_video(
                    slides, narration, audio, directory,
                    declared_diagnostic_voice="EXTERNAL WAV TECHNICAL CANDIDATE NOT FORMAL",
                    ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin,
                )
                if (video.get("status") != "DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION"
                        or video.get("slide_count") != item["slide_count"]
                        or video.get("all_slide_midpoints_source_pixel_checked") is not True
                        or video.get("publication_allowed") is not False
                        or video.get("formal_voice_authorized") is not False
                        or video.get("rendered_pdf_sha256") != item["rendered_pdf_sha256"]
                        or len(video.get("video_slide_frame_alignment", [])) != item["slide_count"]):
                    raise PrivateChapterMediaError("Independent video mux/frame QA not accepted")
                name = "section_" + section.replace(".", "_")
                mp4 = temp / "section_videos" / (name + "_PRIVATE_NOT_PUBLISHED.mp4")
                (directory / "lecture_diagnostic_only.mp4").rename(mp4)
                item["private_video_file"] = str(Path("section_videos") / mp4.name).replace("\\", "/")
                item["private_video_sha256"] = sha_file(mp4)
                item["private_video_seconds"] = video["diagnostic_mp4_duration_seconds"]
                item["every_slide_midpoint_frame_verified"] = True
                shutil.rmtree(directory)
        if any(sha_file(path) != digest for path, digest in frozen.items()):
            raise PrivateChapterMediaError("Original chapter, capture or audio changed during campaign")
        result = {
            "schema_version": 1,
            "status": ("PRIVATE_CHAPTER_EXTERNAL_WAV_VIDEO_CANDIDATES_NOT_PUBLISHED"
                       if render_private_videos else
                       "PRIVATE_CHAPTER_EXTERNAL_WAV_INTAKE_VERIFIED_NOT_PUBLISHED"),
            "chapter_id": receipt["chapter_id"],
            "chapter_readiness_receipt_sha256": sha_file(
                bundle / "chapter_private_readiness_receipt.json"),
            "section_count": len(rows),
            "slide_count": sum(item["slide_count"] for item in rows),
            "total_audio_seconds": round(sum(item["total_audio_seconds"] for item in rows), 3),
            "external_wavs_technically_verified": True,
            "videos_created": render_private_videos,
            "independent_acoustic_word_pronunciation_proven": False,
            "independent_provider_identity_proven": False,
            "voice_distribution_rights_proven": False,
            "academic_semantic_approval_proven": False,
            "formal_voice_authorization_claimed": False,
            "publication_allowed": False,
            "cloud_provider_calls": 0,
            "local_language_model_invocations": 0,
            "sections": rows,
        }
        (temp / "chapter_private_audio_video_receipt.json").write_text(
            json.dumps(result, indent=2), encoding="utf8")
        if output.exists() or output.is_symlink():
            raise PrivateChapterMediaError("Chapter output appeared before atomic commit")
        os.rename(temp, output)
        return result
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter-bundle", required=True, type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--new-private-plan", type=Path)
    parser.add_argument("--capture-plan", type=Path)
    parser.add_argument("--new-private-output", type=Path)
    parser.add_argument("--render-private-videos", action="store_true")
    args = parser.parse_args(argv)
    if args.source_manifest and args.new_private_plan and not (
            args.capture_plan or args.new_private_output or args.render_private_videos):
        result = make_chapter_capture_plan(args.chapter_bundle, args.source_manifest)
        target = _destination(args.new_private_plan, {
            _private_directory(args.chapter_bundle),
            _file(args.source_manifest),
        })
        with target.open("x", encoding="utf8") as file:
            json.dump(result, file, indent=2)
        summary = {"chapter": result["chapter_id"],
                   "sections_waiting_for_authorized_audio": len(result["sections"]),
                   "publication_allowed": False}
    elif args.capture_plan and args.new_private_output and not (
            args.source_manifest or args.new_private_plan):
        result = audit_chapter_captured_audio(
            args.chapter_bundle, args.capture_plan, args.new_private_output,
            render_private_videos=args.render_private_videos)
        summary = {"status": result["status"], "sections": result["section_count"],
                   "slides": result["slide_count"], "publication_allowed": False}
    else:
        parser.error("Choose fresh private capture plan OR complete WAV intake/optional video")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
