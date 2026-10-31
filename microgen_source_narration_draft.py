"""SHA-bound, voice-neutral narration draft QA against a verified source work order.

This validates completeness, fidelity of slide IDs and explicit sensitive terms.
It cannot prove every academic claim correct and cannot select production TTS.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from microgen_pronunciation_closed_loop import sha_file


class NarrationDraftError(ValueError):
    pass


def assess_narration_draft(handoff_file: Path, narration_file: Path,
                           *, min_words: int = 140, max_words: int = 180) -> dict:
    if not (100 <= min_words <= max_words <= 250):
        raise NarrationDraftError("Invalid bounded narration word limits")
    handoff_file = Path(handoff_file)
    narration_file = Path(narration_file)
    if (handoff_file.is_symlink() or narration_file.is_symlink()
            or not handoff_file.is_file() or not narration_file.is_file()):
        raise NarrationDraftError("Independent immutable narration sources required")
    h_digest = sha_file(handoff_file)
    n_digest = sha_file(narration_file)
    h = json.loads(handoff_file.read_text(encoding="utf8"))
    n = json.loads(narration_file.read_text(encoding="utf8"))
    if (h.get("status") != "HANDOFF_CREATED_MEDIA_NOT_READY"
            or h.get("publication_allowed") is not False
            or h.get("formal_voice_authorized") is not False
            or h.get("generated_wavs") is not False
            or h.get("generated_mp4s") is not False
            or n.get("schema_version") != 1
            or not isinstance(n.get("narrations"), list)
            or len(n["narrations"]) != h.get("slide_count")
            or not 1 <= h["slide_count"] <= 60):
        raise NarrationDraftError("Invalid or falsely approved voice-neutral work order")
    work = h["narration_work_order"]
    if len(work) != len(n["narrations"]):
        raise NarrationDraftError("Narration count differs from source slide count")
    rows = []
    for i, (item, src) in enumerate(zip(n["narrations"], work), 1):
        if (not isinstance(item, dict) or type(item.get("slide")) is not int
                or item["slide"] != i or src.get("slide") != i
                or src.get("source_pdf_sha256") != h["source_pdf_sha256"]
                or src.get("draft_pdf_sha256") != h["draft_pdf_sha256"]
                or src.get("publication_allowed") is not False):
            raise NarrationDraftError("Slide source mapping is not complete or sequential")
        words = str(item.get("text", "")).split()
        if not min_words <= len(words) <= max_words:
            raise NarrationDraftError(f"Slide {i} narration word count out of bounds")
        speech = " ".join(words)
        if (not speech.isascii() or len(speech) > 2400
                or re.search(r"\\(?:begin|end|frac|includegraphics)\\b|<[^>]*>", speech)
                or speech.lower().startswith(("this slide", "on this slide"))
                or item.get("academic_review_status") not in
                   ("AUTOMATED_SOURCE_CHECK_PENDING", "ACADEMIC_QA_PENDING")):
            raise NarrationDraftError("Unsafe, ungrounded or misclassified spoken narration")
        # A tiny, universal lexical guard.  Detailed academic facts require a
        # separate source-grounded verifier; a long narration is not proof.
        rows.append({
            "slide": i, "title": src["title"], "source_page": src["source_page"],
            "source_pdf_sha256": src["source_pdf_sha256"],
            "spoken_text_sha256": __import__("hashlib").sha256(
                speech.encode("utf-8")).hexdigest(),
            "word_count": len(words), "narration": speech,
            "review_state": "DRAFT_NEEDS_INDEPENDENT_ACADEMIC_QA",
            "formal_voice": None, "production_audio": None
        })
    if (sha_file(handoff_file) != h_digest or sha_file(narration_file) != n_digest):
        raise NarrationDraftError("Source changed during narration validation")
    return {
        "schema_version": 1,
        "status": "EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED",
        "handoff_sha256": h_digest, "draft_input_sha256": n_digest,
        "source_pdf_sha256": h["source_pdf_sha256"],
        "draft_pdf_sha256": h["draft_pdf_sha256"],
        "slide_count": len(rows), "slides": rows,
        "narration_word_count": sum(x["word_count"] for x in rows),
        "all_slide_texts_present": True,
        "academic_accuracy_independently_verified": False,
        "formal_voice_authorized": False, "provider_calls": 0,
        "generated_wavs": False, "generated_mp4s": False,
        "publication_allowed": False
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--new-report", type=Path, required=True)
    args = parser.parse_args(argv)
    out = args.new_report.resolve(strict=False)
    if (args.new_report.is_symlink() or args.new_report.exists()
            or not out.parent.is_dir()
            or any(v.casefold() == "my drive" for v in out.parts)
            or out.parent in [args.handoff.resolve().parent, args.narration.resolve().parent]):
        raise NarrationDraftError("Fresh independent output report required")
    report = assess_narration_draft(args.handoff, args.narration)
    with out.open("x", encoding="utf8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps({"report": str(out), "slides": report["slide_count"],
                      "narration_words": report["narration_word_count"],
                      "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
