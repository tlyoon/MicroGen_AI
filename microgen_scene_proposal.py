"""Propose source-grounded lecture scenes for manual approval before multipart.

No Gemini calls. A proposal is NOT an approved lesson. The proposed topic
boundaries and textbook page citations must be inspected before use.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from microgen_quality import sha256
from microgen_multipart import MultipartError, validate_scenes


def _words(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z]{4,}", text.lower())
            if x not in {"slide", "page", "chapter", "section", "integral", "calculus",
                         "figure", "example", "lecture", "part", "continued"}}


def _heading(page) -> str:
    lines = [x.strip() for x in page.get_text("text").splitlines()
             if x.strip() and not re.fullmatch(r"\d+\s*/\s*\d+", x.strip())]
    if not lines:
        raise MultipartError("No readable heading on slide")
    # First line is generally the Beamer heading, but the first slide may be
    # its large lesson title. Retain unmodified words for reviewer QA.
    candidate = lines[0][:130]
    if not _words(candidate):
        candidate = next((x[:130] for x in lines if _words(x)), "")
    if not candidate:
        raise MultipartError("Unable to identify slide topic")
    return candidate


def build_proposal(stage: Path) -> dict:
    stage = Path(stage)
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    with fitz.open(stage / "source.pdf") as doc:
        pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    with fitz.open(stage / "slides.pdf") as doc:
        headings = [_heading(doc[i]) for i in range(doc.page_count)]
    scenes = []
    for slide_id, heading in enumerate(headings, 1):
        compact = re.sub(r"\s*\((?:continued|part\s*\d+)\)\s*$",
                         "", heading, flags=re.I).strip().casefold()
        if scenes and scenes[-1]["canonical_topic"] == compact:
            scenes[-1]["slides"].append(slide_id)
            continue
        tokens = _words(heading)
        overlaps = [(len(tokens & _words(p)), idx + 1) for idx, p in enumerate(pages)]
        overlaps.sort(reverse=True)
        best = overlaps[0] if overlaps else (0, 0)
        # A weak automatic match is *never* an accepted provenance claim.
        page_refs = [best[1]] if best[0] >= 2 else []
        scenes.append({
            "canonical_topic": compact, "topic": heading, "slides": [slide_id],
            "source_pages": page_refs,
            "natural_break_after": True,
            "evidence_tokens": best[0],
            "needs_review": best[0] < 2,
        })
    for scene in scenes:
        scene.pop("canonical_topic")
    if scenes:
        scenes[-1]["natural_break_after"] = True
    return {
        "schema_version": 1,
        "reviewed": False,
        "reviewer": "",
        "source_sha256": sha256(stage / "source.pdf"),
        "slides_sha256": sha256(stage / "slides.pdf"),
        "scenes": scenes,
        "warning": "PROPOSAL ONLY. Inspect all source page citations and semantic breaks. "
                   "Correct weak matches before marking reviewed.",
    }


def main() -> int:
    ap=argparse.ArgumentParser(description="Create/approve read-only source-grounded multipart scene proposal")
    ap.add_argument("--stage",required=True,type=Path)
    ap.add_argument("--approve",action="store_true",help="Use previously curated proposal")
    ap.add_argument("--reviewer",default="",help="Required identity for reviewed approval")
    args=ap.parse_args()
    if args.approve:
        proposal=args.stage/"lesson_scenes.proposal.json"
        if not proposal.is_file():
            raise MultipartError("No proposal to approve")
        data=json.loads(proposal.read_text(encoding="utf-8"))
        if not args.reviewer.strip():
            raise MultipartError("Reviewer acknowledgment is required")
        if any(s.get("needs_review") for s in data["scenes"]):
            raise MultipartError("Curate weakly grounded scenes before approval")
        # Explicit field curation required for every listed citation and break.
        reviewed={**data,"reviewed":True,"reviewer":args.reviewer.strip()}
        out=args.stage/"lesson_scenes.json"
        if out.exists():
            raise MultipartError("Approved plan exists; avoid overwrite")
        out.write_text(json.dumps(reviewed,indent=2,ensure_ascii=False),encoding="utf-8")
        try:
            # Approval occurs before costly narration/TTS: WAVs do not yet exist.
            import fitz
            with fitz.open(args.stage / "slides.pdf") as document:
                total = document.page_count
            validate_scenes(args.stage, durations=[1.0] * total)
        except Exception:
            out.unlink(missing_ok=True)
            raise
        print(f"REVIEWED_SCENE_MANIFEST {out}")
        return 0
    result=build_proposal(args.stage)
    output=args.stage/"lesson_scenes.proposal.json"
    if output.exists():
        raise MultipartError("Existing proposal; review before replacing")
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"PROPOSAL_WRITTEN {output}; SCENES={len(result['scenes'])}; "
          f"REVIEW_REQUIRED={sum(s['needs_review'] for s in result['scenes'])}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
