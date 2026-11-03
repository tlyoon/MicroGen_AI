"""Provider-neutral PRIVATE formal-voice input handoff for source-bound lessons.

This exports *requests*, not speech: no local model, external provider,
billing, voice substitution, authorization, or publishing is performed.
It operates on existing validated stage/slide receipts without re-rendering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import pymupdf as fitz

from microgen_portable_section_contract import audit_portable_contract
from microgen_pronunciation_closed_loop import sha_file


class PortableVoiceHandoffError(ValueError):
    pass


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 10 <= path.stat().st_size <= 2_000_000:
        raise PortableVoiceHandoffError("Expected a bounded private JSON file")
    try:
        obj = json.loads(path.read_text(encoding="utf8"))
    except (UnicodeError, ValueError) as exc:
        raise PortableVoiceHandoffError("Malformed private source receipt") from exc
    if not isinstance(obj, dict):
        raise PortableVoiceHandoffError("Private input must be a JSON object")
    return obj


def prepare_portable_voice_input_handoff(stage: Path, slides: Path) -> dict:
    """Independently verify immutable source->deck->spoken text SHA binding."""
    stage, slides = Path(stage), Path(slides)
    if (stage.is_symlink() or slides.is_symlink() or
            not stage.is_dir() or not slides.is_dir()):
        raise PortableVoiceHandoffError("Regular private stage and slide directories required")
    files = {
        "source_pdf": stage / "source.pdf",
        "narration": stage / "narration.json",
        "visual_plan": stage / "plan.json",
        "contract": stage / "contract.json",
        "rendered_pdf": slides / "slides_teaching_candidate.pdf",
        "slide_receipt": slides / "teaching_slide_receipt.json",
    }
    if any(p.is_symlink() or not p.is_file() for p in files.values()):
        raise PortableVoiceHandoffError("Missing or symlinked protected source evidence")
    originals = {name: sha_file(path) for name, path in files.items()}
    n = _read_json(files["narration"])
    v = _read_json(files["visual_plan"])
    m = _read_json(files["contract"])
    receipt = _read_json(files["slide_receipt"])
    try:
        audit = audit_portable_contract(
            files["source_pdf"], files["narration"],
            files["visual_plan"], files["contract"])
    except Exception as exc:
        raise PortableVoiceHandoffError("Original source-bound authoring contract failed") from exc
    count = audit.get("topic_count")
    if (type(count) is not int or not 2 <= count <= 20 or
            receipt.get("status") != "PORTABLE_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED" or
            receipt.get("slide_count") != count or
            receipt.get("section_id") != m.get("section_id") or
            receipt.get("source_pdf_sha256") != originals["source_pdf"] or
            receipt.get("narration_qa_sha256") != originals["narration"] or
            receipt.get("visual_plan_sha256") != originals["visual_plan"] or
            receipt.get("portable_contract_sha256") != originals["contract"] or
            receipt.get("rendered_pdf_sha256") != originals["rendered_pdf"] or
            receipt.get("figures_exact_original_pixels_verified") is not True or
            any(value.get("publication_allowed") is not False
                for value in (n, m, receipt)) or
            n.get("formal_voice_authorized") is not False or
            receipt.get("formal_voice_authorized") is not False or
            not isinstance(n.get("slides"), list) or len(n["slides"]) != count or
            not isinstance(v.get("slides"), list) or len(v["slides"]) != count or
            not isinstance(receipt.get("slides"), list) or len(receipt["slides"]) != count or
            not isinstance(m.get("topics"), list) or len(m["topics"]) != count):
        raise PortableVoiceHandoffError("Incomplete, mutable or falsely authorized deck identity")
    with fitz.open(files["rendered_pdf"]) as document:
        if len(document) != count:
            raise PortableVoiceHandoffError("Rendered deck page count drift")
    requests = []
    for i, (spoken, visual, proof, topic) in enumerate(zip(
            n["slides"], v["slides"], receipt["slides"], m["topics"]), 1):
        speech = spoken.get("narration")
        anchor = spoken.get("spoken_text_sha256")
        if (not isinstance(speech, str) or not speech.isascii() or
                not 60 <= len(speech.split()) <= 250 or
                not isinstance(anchor, str) or
                hashlib.sha256(speech.encode("utf8")).hexdigest() != anchor or
                any(row.get("slide") != i or row.get("topic_id") != topic.get("topic_id")
                    or row.get("source_page") != topic.get("source_page")
                    for row in (spoken, visual, proof)) or
                proof.get("narration_sha256") != anchor or
                visual.get("title") != proof.get("title") or
                visual.get("bullets") != proof.get("bullets")):
            raise PortableVoiceHandoffError("Rendered lesson differs from exact spoken input")
        requests.append({
            "slide": i, "topic_id": topic["topic_id"],
            "source_page": topic["source_page"],
            "input_text": speech, "text_sha256": anchor,
            "audio_filename": None, "audio_sha256": None,
            "pronunciation_acoustically_verified": False,
            "formal_synthesis_authorized": False,
        })
    if any(sha_file(path) != digest for name, path in files.items()
           for digest in [originals[name]]):
        raise PortableVoiceHandoffError("Source or rendered artifact changed during handoff")
    return {
        "schema_version": 1,
        "status": "PORTABLE_VOICE_INPUT_READY_FORMAL_PRODUCTION_BLOCKED",
        "section_id": m["section_id"], "slide_count": count,
        "source_pdf_sha256": originals["source_pdf"],
        "contract_sha256": originals["contract"],
        "narration_sha256": originals["narration"],
        "rendered_pdf_sha256": originals["rendered_pdf"],
        "render_receipt_sha256": originals["slide_receipt"],
        "language_code": "en-US",
        "requested_audio_format": "mono-pcm16-wav",
        "formal_voice_provider": None, "formal_voice_name": None,
        "provider_calls": 0, "local_model_invocations": 0,
        "source_figure_caption_semantics_fully_verified": False,
        "complete_scientific_semantics_verified": False,
        "formal_voice_synthesis_authorized": False,
        "publication_allowed": False,
        "blocking_conditions": [
            "FORMAL_TTS_PROVIDER_AND_VOICE_REQUIRE_AUTHORIZATION",
            "FORMAL_WAV_AND_SYNCHRONIZED_VIDEO_NOT_GENERATED",
            "ACOUSTIC_PRONUNCIATION_NOT_VERIFIED",
            "PUBLICATION_RIGHTS_NOT_VERIFIED",
        ],
        "requests": requests,
    }


def save_portable_voice_input_handoff(stage: Path, slides: Path, output: Path) -> dict:
    """Create a new private JSON file outside source, stage, and rendered folders."""
    stage, slides, output = Path(stage), Path(slides), Path(output)
    target = output.resolve(strict=False)
    stage_real = stage.resolve(strict=True)
    slides_real = slides.resolve(strict=True)
    if (output.exists() or output.is_symlink() or not target.parent.is_dir()
            or any(x.casefold() == "my drive" for x in target.parts)
            or target == stage_real or stage_real in target.parents
            or target == slides_real or slides_real in target.parents
            or target in stage_real.parents or target in slides_real.parents):
        raise PortableVoiceHandoffError("Fresh separate private destination required")
    report = prepare_portable_voice_input_handoff(stage, slides)
    fd, temporary = tempfile.mkstemp(prefix=".microgen-private-voice-",
                                    suffix=".json", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(report, stream, indent=2)
        if target.exists():
            raise PortableVoiceHandoffError("Destination appeared during handoff")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-stage", type=Path, required=True)
    parser.add_argument("--private-slides", type=Path, required=True)
    parser.add_argument("--new-private-output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = save_portable_voice_input_handoff(
        args.private_stage, args.private_slides, args.new_private_output)
    # Do not echo protected narration, original source or paths.
    print(json.dumps({"section": result["section_id"],
        "tts_requests_ready": result["slide_count"],
        "provider_calls": 0, "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
