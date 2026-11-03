"""Discover external chapter WAVs and auto-build SHA-bound capture manifests.

For an incomplete drop, publish ONE private inventory (no accepted manifest).
For a complete drop with explicitly declared voice/provider labels, atomically
publish validated capture JSONs and a ready-to-run PR268 chapter input plan.
Never synthesizes audio, guesses a provider, calls a model, or approves release.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import wave

from microgen_portable_audio_import import (
    audit_portable_audio_import, make_audio_capture_template,
)
from microgen_private_chapter_audio_video import (
    PrivateChapterMediaError, _chapter, _destination, _file, _frozen,
    _input_plan, _private_directory,
)
from microgen_portable_voice_input_handoff import _read_json
from microgen_pronunciation_closed_loop import sha_file
from microgen_tts_wave_integrity import require_structurally_usable_audio


class ChapterCaptureDiscoveryError(ValueError):
    """No safe identity-proven chapter input or destination."""


def _labels(path: Path | None, sections: list[str], frozen: dict) -> dict:
    if path is None:
        return {}
    path = _file(Path(path))
    _frozen(frozen, path)
    doc = _read_json(path)
    if (set(doc) != {"schema_version", "sections",
                    "formal_voice_authorization_claimed", "publication_allowed"}
            or doc["schema_version"] != 1
            or doc["formal_voice_authorization_claimed"] is not False
            or doc["publication_allowed"] is not False
            or not isinstance(doc["sections"], list)
            or len(doc["sections"]) != len(sections)):
        raise ChapterCaptureDiscoveryError("Explicit private voice declarations invalid")
    result = {}
    for expect, item in zip(sections, doc["sections"]):
        if not isinstance(item, dict) or set(item) != {
                "section_id", "declared_provider", "declared_voice"} or item["section_id"] != expect:
            raise ChapterCaptureDiscoveryError("Voice labels are missing or reordered")
        provider, voice = item["declared_provider"], item["declared_voice"]
        # Null means the owner has NOT yet identified the provider/voice. Do not guess.
        if (provider is None and voice is None):
            result[expect] = None
        elif (isinstance(provider, str) and isinstance(voice, str)
              and 2 <= len(provider) <= 80 and 2 <= len(voice) <= 80
              and provider.isascii() and voice.isascii()
              and provider.strip() == provider and voice.strip() == voice):
            result[expect] = (provider, voice)
        else:
            raise ChapterCaptureDiscoveryError("Malformed or partially claimed voice provider identity")
    return result


def make_private_declarations_template(chapter_bundle: Path) -> dict:
    frozen = {}
    chapter, verified = _chapter(chapter_bundle, frozen)
    return {
        "schema_version": 1,
        "sections": [{"section_id": section, "declared_provider": None,
                      "declared_voice": None}
                     for section, _, _ in verified],
        "formal_voice_authorization_claimed": False,
        "publication_allowed": False,
    }


def discover_chapter_wavs(
    chapter_bundle: Path,
    blank_input_plan: Path,
    wav_root: Path,
    new_output: Path,
    *,
    declarations: Path | None = None,
) -> dict:
    """Produce consolidated private missing/invalid inventory or complete valid manifests.

    Input plan is the untouched PR268 source-bound plan with null audio paths.
    Audio drop structure is root/section_1_1/slide01.wav etc.
    """
    frozen = {}
    bundle = _private_directory(chapter_bundle)
    chapter, verified = _chapter(bundle, frozen)
    cases = _input_plan(
        blank_input_plan, dict(chapter, _bundle=str(bundle)), frozen)
    root = _private_directory(wav_root)
    expected_sections = [section for section, _, _ in verified]
    declared = _labels(declarations, expected_sections, frozen)
    if len(cases) != len(verified):
        raise ChapterCaptureDiscoveryError("Chapter plan section inventory drifted")
    protected = {bundle, root}
    rows = []
    captures = []
    ready = True
    for case, (section, source_row, handoff_path) in zip(cases, verified):
        if (not isinstance(case, dict) or set(case) != {
                "section_id", "source_pdf", "slides_dir", "narration_qa",
                "audio_dir", "capture_manifest"}
                or case["section_id"] != section
                or case["audio_dir"] is not None
                or case["capture_manifest"] is not None):
            raise ChapterCaptureDiscoveryError("Expected original blank PR268 source-bound plan")
        source = _file(Path(case["source_pdf"]))
        slides = _private_directory(Path(case["slides_dir"]))
        narration = _file(Path(case["narration_qa"]))
        protected.update((slides, narration.parent))
        if (_frozen(frozen, source) != source_row["original_source_sha256"]
                or _frozen(frozen, narration) != source_row["narration_sha256"]
                or _frozen(frozen, slides/"slides_teaching_candidate.pdf") !=
                source_row["rendered_pdf_sha256"]):
            raise ChapterCaptureDiscoveryError("Original PDF/slide/narration source SHA drifted")
        _frozen(frozen, slides/"teaching_slide_receipt.json")
        folder_name = "section_" + section.replace(".", "_")
        wav_dir = root / folder_name
        template = make_audio_capture_template(handoff_path)
        names = [row["filename"] for row in template["captured_wavs"]]
        missing, invalid, extras = [], [], []
        available = []
        if wav_dir.is_symlink() or (wav_dir.exists() and not wav_dir.is_dir()):
            invalid.append("unsafe_section_directory")
            missing = list(names)
        elif not wav_dir.exists():
            missing = list(names)
        else:
            directory = _private_directory(wav_dir)
            actual = {p.name for p in directory.iterdir()
                      if p.suffix.casefold() == ".wav"}
            extras = sorted(actual - set(names))
            # Uppercase or mixed-case WAV names count as unexpected, not silently renamed.
            for name in names:
                item = directory/name
                if name not in actual or not item.is_file() or item.is_symlink():
                    missing.append(name)
                    if item.is_symlink():
                        invalid.append(name)
                    continue
                try:
                    if not 1 <= item.stat().st_size <= 30_000_000:
                        raise ValueError("Audio file size invalid")
                    require_structurally_usable_audio(item)
                    with wave.open(str(item), "rb") as audio:
                        seconds = audio.getnframes()/audio.getframerate()
                    if not 0.2 <= seconds <= 180:
                        raise ValueError("Duration outside accepted slide range")
                    value = _frozen(frozen, item)
                    available.append((name, value))
                except (OSError, ValueError, wave.Error, EOFError, ZeroDivisionError):
                    invalid.append(name)
        label = declared.get(section)
        complete = (not missing and not invalid and not extras
                    and len(available) == len(names) and label is not None)
        ready = ready and complete
        rows.append({
            "section_id": section,
            "required_wav_count": len(names),
            "structurally_usable_wav_count": len(available),
            "missing_wav_files": missing,
            "unexpected_wav_files": extras,
            "invalid_wav_files": invalid,
            "provider_and_voice_explicitly_declared": label is not None,
            "eligible_for_capture_manifest": complete,
            "publication_allowed": False,
        })
        captures.append((section, template, available, wav_dir, case, label))
    output = _destination(Path(new_output), protected | set(frozen))
    temp = Path(tempfile.mkdtemp(prefix=".microgen-chapter-capture-", dir=output.parent))
    try:
        populated = []
        if ready:
            (temp/"capture_manifests").mkdir()
            for section, template, available, wav_dir, case, label in captures:
                hashes = dict(available)
                template["declared_provider"], template["declared_voice"] = label
                for clip in template["captured_wavs"]:
                    clip["wav_sha256"] = hashes[clip["filename"]]
                name = "section_" + section.replace(".", "_") + "_capture.json"
                capture_file = temp/"capture_manifests"/name
                capture_file.write_text(json.dumps(template, indent=2), encoding="utf8")
                request_file = bundle/"voice_inputs"/(
                    "section_" + section.replace(".", "_") + ".json")
                confirmed = audit_portable_audio_import(
                    request_file, wav_dir, capture_file)
                if (confirmed["section_id"] != section
                        or confirmed["slide_count"] != len(available)
                        or confirmed["publication_allowed"] is not False):
                    raise ChapterCaptureDiscoveryError("Completed captured audio failed proven PR265 audit")
                final_case = dict(case)
                final_case["audio_dir"] = str(wav_dir)
                final_case["capture_manifest"] = str(
                    output/"capture_manifests"/name)
                populated.append(final_case)
            plan = {
                "schema_version": 1,
                "chapter_id": chapter["chapter_id"],
                "chapter_receipt_sha256": sha_file(
                    bundle/"chapter_private_readiness_receipt.json"),
                "sections": populated,
                "formal_voice_authorization_claimed": False,
                "publication_allowed": False,
            }
            (temp/"capture_plan_ready.json").write_text(
                json.dumps(plan, indent=2), encoding="utf8")
        if any(sha_file(path) != digest for path, digest in frozen.items()):
            raise ChapterCaptureDiscoveryError("Protected original, label or WAV altered during scan")
        result = {
            "schema_version": 1,
            "status": ("PRIVATE_CHAPTER_CAPTURE_MANIFESTS_READY_NOT_PUBLISHED"
                       if ready else "PRIVATE_CHAPTER_CAPTURE_INVENTORY_INCOMPLETE_NOT_PUBLISHED"),
            "chapter_id": chapter["chapter_id"],
            "chapter_readiness_receipt_sha256": sha_file(
                bundle/"chapter_private_readiness_receipt.json"),
            "section_count": len(rows),
            "required_wav_count": sum(x["required_wav_count"] for x in rows),
            "structurally_usable_wav_count": sum(
                x["structurally_usable_wav_count"] for x in rows),
            "sections_ready_for_import": sum(x["eligible_for_capture_manifest"]
                                              for x in rows),
            "missing_audio_files_total": sum(len(x["missing_wav_files"]) for x in rows),
            "unexpected_audio_files_total": sum(
                len(x["unexpected_wav_files"]) for x in rows),
            "invalid_audio_files_total": sum(len(x["invalid_wav_files"]) for x in rows),
            "complete_capture_plan_written": ready,
            "provider_identity_independently_verified": False,
            "narration_words_actually_spoken_verified": False,
            "formal_voice_synthesis_authorized": False,
            "publication_allowed": False,
            "local_language_model_invocations": 0,
            "provider_calls": 0,
            "sections": rows,
        }
        (temp/"chapter_capture_discovery_receipt.json").write_text(
            json.dumps(result, indent=2), encoding="utf8")
        if output.exists() or output.is_symlink():
            raise ChapterCaptureDiscoveryError("Output appeared during atomic capture preparation")
        os.rename(temp, output)
        return result
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter-bundle", required=True, type=Path)
    ap.add_argument("--new-declarations-template", type=Path)
    ap.add_argument("--blank-input-plan", type=Path)
    ap.add_argument("--wav-root", type=Path)
    ap.add_argument("--declarations", type=Path)
    ap.add_argument("--new-private-output", type=Path)
    args = ap.parse_args(argv)
    if (args.new_declarations_template and not args.blank_input_plan
            and not args.wav_root and not args.declarations
            and not args.new_private_output):
        target = _destination(args.new_declarations_template,
                              {_private_directory(args.chapter_bundle)})
        result = make_private_declarations_template(args.chapter_bundle)
        target.write_text(json.dumps(result, indent=2), encoding="utf8")
        summary = {"sections_needing_truthful_provider_declarations":
                   len(result["sections"]), "publication_allowed": False}
    elif (args.blank_input_plan and args.wav_root and args.new_private_output
          and not args.new_declarations_template):
        result = discover_chapter_wavs(
            args.chapter_bundle, args.blank_input_plan, args.wav_root,
            args.new_private_output, declarations=args.declarations)
        summary = {
            "status": result["status"], "sections": result["section_count"],
            "wav_files_found_usable": result["structurally_usable_wav_count"],
            "wav_files_missing": result["missing_audio_files_total"],
            "complete_plan_ready": result["complete_capture_plan_written"],
            "publication_allowed": False,
        }
    else:
        ap.error("Choose a fresh declaration template OR full chapter WAV discovery")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
