"""Source-verified Chapter TTS: Gemini Flash-Lite -> Flash -> opt-in Cloud.

API-based original MicroGen_AI ONLY; no Selenium, no local LLM.
Default operation is zero-charge read-only preflight. An explicit paid-run
flag is necessary before any 57-request Chapter1 synthesis is performed.
Feeds existing PR267 original handoffs, PR269 WAV capture and PR268 video QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from microgen_flash_tts import (
    render_batch, DEFAULT_VOICE, CLOUD_FALLBACK_ENV, CLOUD_MAX_CHARS_ENV,
)
from microgen_portable_voice_input_handoff import _read_json
from microgen_private_chapter_audio_video import (
    PrivateChapterMediaError, _chapter, _file, _frozen, _input_plan,
    _destination, _private_directory,
)
from microgen_private_chapter_capture_discovery import (
    discover_chapter_wavs, make_private_declarations_template,
)
from microgen_pronunciation_closed_loop import sha_file
from microgen_tts_provider_policy import selected_formal_provider


class FlashChapterTTSError(ValueError):
    """Invalid original chapter, voice authorization, or output contract."""


def chapter_preflight(chapter_bundle: Path, blank_source_plan: Path) -> tuple[dict, list, dict]:
    """Verify the exact original source-bound 57-request handoff without API calls."""
    frozen = {}
    bundle = _private_directory(chapter_bundle)
    receipt, originals = _chapter(bundle, frozen)
    cases = _input_plan(blank_source_plan, dict(receipt, _bundle=str(bundle)), frozen)
    if len(cases) != len(originals):
        raise FlashChapterTTSError("Chapter section count drifted")
    requests, sections = [], []
    for case, (section, row, handoff_path) in zip(cases, originals):
        if (not isinstance(case, dict)
                or case.get("section_id") != section
                or case.get("audio_dir") is not None
                or case.get("capture_manifest") is not None):
            raise FlashChapterTTSError("Complete unchanged PR268 blank plan required")
        source = _file(Path(case["source_pdf"]))
        slides = _private_directory(Path(case["slides_dir"]))
        narration = _file(Path(case["narration_qa"]))
        if (_frozen(frozen, source) != row["original_source_sha256"]
                or _frozen(frozen, narration) != row["narration_sha256"]
                or _frozen(frozen, slides/"slides_teaching_candidate.pdf") !=
                row["rendered_pdf_sha256"]):
            raise FlashChapterTTSError("Current Chapter 1 original source/slide/narration drift")
        handoff = _read_json(_file(handoff_path))
        if (handoff["section_id"] != section or
                handoff["slide_count"] != len(handoff["requests"]) or
                handoff["formal_voice_synthesis_authorized"] is not False or
                handoff["publication_allowed"] is not False):
            raise FlashChapterTTSError("Original voice handoff invalid or falsely approved")
        for i, item in enumerate(handoff["requests"], 1):
            words = item["input_text"]
            if (item["slide"] != i or item["text_sha256"] !=
                    hashlib.sha256(words.encode("utf8")).hexdigest()):
                raise FlashChapterTTSError("Narration text SHA mismatch")
            requests.append(words)
        sections.append({
            "section_id": section,
            "slides": handoff["slide_count"],
            "request_sha256": sha_file(handoff_path),
            "source_sha256": handoff["source_pdf_sha256"],
            "rendered_deck_sha256": handoff["rendered_pdf_sha256"],
        })
    if (sum(s["slides"] for s in sections) !=
            receipt["total_teaching_slides"] or
            len(requests) != receipt["total_voice_requests"]):
        raise FlashChapterTTSError("Entire chapter requests incomplete")
    if any(sha_file(p) != digest for p,digest in frozen.items()):
        raise FlashChapterTTSError("Original chapter data changed during preflight")
    result = {
        "status": "SOURCE_BOUND_GEMINI_FLASH_TTS_CHAPTER_PREFLIGHT_NOT_PUBLISHED",
        "chapter_id": receipt["chapter_id"],
        "section_count": len(sections),
        "slide_count": len(requests),
        "characters": sum(map(len,requests)),
        "gemini_default_model": "gemini-3.8-flash-lite-tts",
        "gemini_first_fallback": "gemini-3.8-flash-tts",
        "voice": DEFAULT_VOICE,
        "formal_provider_selector": selected_formal_provider(),
        "cloud_is_last_optional_fallback": True,
        "paid_provider_calls": 0,
        "publication_allowed": False,
        "sections": sections,
    }
    return result, requests, frozen


def produce_private_chapter(
    chapter_bundle: Path, blank_source_plan: Path, fresh_output: Path, *,
    authorized_paid_run: bool = False,
    allow_cloud: bool = False,
    voice: str = DEFAULT_VOICE,
    speak=None,
) -> dict:
    """Paying providers are never contacted without an explicit bounded operator opt-in."""
    info, words, frozen = chapter_preflight(chapter_bundle, blank_source_plan)
    if not authorized_paid_run:
        raise FlashChapterTTSError(
            "Paid production needs --authorize-paid-gemini-tts; dry-run is default")
    if info["formal_provider_selector"] != "gemini":
        raise FlashChapterTTSError("Formal provider is not Gemini; no silent provider switch")
    output = _destination(fresh_output, {
        _private_directory(chapter_bundle), _file(blank_source_plan),
        *frozen.keys(),
    })
    temp = Path(tempfile.mkdtemp(prefix=".microgen-flash-chapter-",dir=output.parent))
    try:
        raw = render_batch(words, temp/"flat_full_chapter_audio", voice=voice,
                           allow_cloud=allow_cloud,speak=speak)
        if (raw["slide_count"] != len(words)
                or raw["voice"] not in (voice, f"en-US-Chirp3-HD-{voice}")
                or raw["publication_allowed"] is not False):
            raise FlashChapterTTSError("TTS provider batch evidence inconsistent")
        (temp/"tts_engine_receipt.json").write_text(
            json.dumps(raw,indent=2),encoding="utf8")
        root = temp/"wav_root"
        root.mkdir()
        labels = make_private_declarations_template(chapter_bundle)
        index = 0
        for section, label in zip(info["sections"], labels["sections"]):
            section_root=root/("section_"+section["section_id"].replace(".","_"))
            section_root.mkdir()
            for n in range(1,section["slides"]+1):
                source=temp/"flat_full_chapter_audio"/f"slide{index+1:02}.wav"
                target=section_root/f"slide{n:02}.wav"
                shutil.copy2(source,target)
                row=raw["slides"][index]
                if (row["wav_sha256"] != sha_file(target) or
                        row["text_sha256"] != hashlib.sha256(words[index].encode("utf8")).hexdigest()):
                    raise FlashChapterTTSError("Private source WAV/text drift during chapter assembly")
                index+=1
            label["declared_provider"] = raw["model"]
            label["declared_voice"] = raw["voice"]
        if index!=len(words):
            raise FlashChapterTTSError("Every chapter request must be captured")
        declaration_path=temp/"generated_provider_voice_declarations_NOT_RELEASE.json"
        declaration_path.write_text(json.dumps(labels,indent=2),encoding="utf8")
        capture=discover_chapter_wavs(
            chapter_bundle,blank_source_plan,root,temp/"verified_capture",
            declarations=declaration_path)
        if (capture["complete_capture_plan_written"] is not True
                or capture["required_wav_count"] != len(words)
                or capture["sections_ready_for_import"] != len(info["sections"])):
            raise FlashChapterTTSError("PR269 chapter capture checker did not approve all WAV inputs")
        # PR269 creates location-bound plan paths; rebase them BEFORE atomic rename.
        plan_path=temp/"verified_capture"/"capture_plan_ready.json"
        plan=_read_json(plan_path)
        for row in plan["sections"]:
            for key in ("audio_dir","capture_manifest"):
                src=Path(row[key]).resolve(strict=False)
                if temp not in src.parents:
                    raise FlashChapterTTSError("Private WAV manifest path escaped staging")
                row[key] = str(output / src.relative_to(temp))
        plan_path.write_text(json.dumps(plan,indent=2),encoding="utf8")
        shutil.rmtree(temp/"flat_full_chapter_audio")
        if any(sha_file(p)!=digest for p,digest in frozen.items()):
            raise FlashChapterTTSError("Original sources changed during audio generation")
        summary={
            "schema_version":1,
            "status":"PRIVATE_CHAPTER_GEMINI_FLASH_TTS_AND_PR269_CAPTURE_COMPLETE_NOT_PUBLISHED",
            "chapter_id":info["chapter_id"],
            "section_count":info["section_count"],
            "slide_count":len(words),
            "narration_characters":info["characters"],
            "provider_model":raw["model"],
            "provider_voice":raw["voice"],
            "fallback_used":raw["fallback_used"],
            "complete_pr268_input_plan":"verified_capture/capture_plan_ready.json",
            "technical_wav_integrity_verified":True,
            "spoken_words_and_pronunciation_independently_verified":False,
            "academic_release_approved":False,
            "copyright_release_approved":False,
            "publication_allowed":False,
        }
        (temp/"chapter_gemini_audio_receipt.json").write_text(
            json.dumps(summary,indent=2),encoding="utf8")
        if output.exists():
            raise FlashChapterTTSError("Output race; refuse to overwrite")
        os.rename(temp,output)
        return summary
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter-bundle",required=True,type=Path)
    ap.add_argument("--blank-source-plan",required=True,type=Path)
    ap.add_argument("--new-private-output",type=Path)
    ap.add_argument("--authorize-paid-gemini-tts",action="store_true")
    ap.add_argument("--allow-cloud-fallback",action="store_true")
    ap.add_argument("--voice",default=DEFAULT_VOICE)
    args=ap.parse_args(argv)
    if not args.authorize_paid_gemini_tts:
        if args.new_private_output is not None or args.allow_cloud_fallback:
            ap.error("Only dry-run without an output is permitted unless explicitly authorized")
        result, _, _ = chapter_preflight(args.chapter_bundle,args.blank_source_plan)
        print(json.dumps(result))
        return 0
    if args.new_private_output is None:
        ap.error("Fresh private output is required for an authorized paid run")
    result=produce_private_chapter(
        args.chapter_bundle,args.blank_source_plan,args.new_private_output,
        authorized_paid_run=True,allow_cloud=args.allow_cloud_fallback,
        voice=args.voice)
    print(json.dumps(result))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
