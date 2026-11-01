"""Deterministic, private-first PDF section passage discovery, not academic approval.

Find source-backed evidence blocks and propose authoring *candidates*, not finished
curriculum. No model, provider, copyright asset export or narration generation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import pymupdf as fitz

from microgen_portable_section_contract import clean
from microgen_pronunciation_closed_loop import sha_file


class SourceDiscoveryError(ValueError):
    pass


def normalized_passage(text: str) -> str:
    """Preserve words from the PDF; remove extraction line-break hyphenation."""
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[\u00ad\u200b-\u200f\ufeff]", "", text)
    return " ".join(text.split())


def _heading_bound(page: fitz.Page, marker: str, first: bool) -> tuple[float, float]:
    """Return a marked text block's vertical bound; reject missing boundaries."""
    candidates = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks", sort=False):
        if clean(marker) in clean(normalized_passage(text)):
            candidates.append((float(y0), float(y1)))
    if not candidates:
        raise SourceDiscoveryError(f"Required section boundary absent: {marker}")
    # A printed header may duplicate an actual section heading near the top.
    # Favor a substantive on-page heading if present, otherwise the first header.
    body = [p for p in candidates if p[0] >= 55]
    pool = body if body else candidates
    return max(pool, key=lambda p: p[0]) if first else min(pool, key=lambda p: p[0])


def _figure_labels(text: str) -> list[str]:
    # Text citations alone cannot prove which image panel a caption describes.
    found = re.findall(r"\bFigure\s+(\d+(?:[.\-]\d+)+)\b", text, flags=re.I)
    return list(dict.fromkeys("Figure " + s.replace("-", ".") for s in found))


def _draft_topic(block: dict) -> dict:
    source = block["text"]
    first_sentence = re.split(r"(?<=[.!?])\s+", source, maxsplit=1)[0]
    # Explicitly source-excerpt suggestions, not original rewritten teaching text.
    snippet = first_sentence[:95].rstrip()
    anchor = source[:min(90, len(source))].rstrip()
    return {
        "candidate_id": block["passage_id"],
        "source_page": block["source_page"],
        "source_bbox": block["source_bbox"],
        "source_sha256": block["source_sha256"],
        "suggested_source_anchor": anchor,
        "source_excerpt_title_not_for_slides": snippet,
        "figure_mentions": block["figure_mentions"],
        "authoring_status": "REQUIRES_INDEPENDENT_ORIGINAL_TEACHING_CONTENT",
        "auto_narration_generated": False,
        "auto_visual_plan_generated": False,
        "scientific_semantics_verified": False,
    }


def discover_passages(source_pdf: Path, start_marker: str,
                      next_marker: str | None = None, *,
                      end_of_pdf: bool = False,
                      contract: Path | None = None) -> dict:
    """Discover geometric source passages inside explicit start/next boundaries.

    The manifest, if provided, is *audited for source identity only*; its stated
    topics do not influence independent passage extraction. Matches are advisory.
    """
    source_pdf = Path(source_pdf)
    if (not source_pdf.is_file() or source_pdf.is_symlink()
        or not isinstance(start_marker, str) or not start_marker.strip()
        or bool(next_marker) == bool(end_of_pdf)
        or (next_marker is not None and
            (not isinstance(next_marker, str) or not next_marker.strip()))):
        raise SourceDiscoveryError("Immutable PDF and explicit section boundaries required")
    original_sha = sha_file(source_pdf)
    m = None
    if contract is not None:
        contract = Path(contract)
        if not contract.is_file() or contract.is_symlink():
            raise SourceDiscoveryError("Source-bound manifest missing or unsafe")
        m = json.loads(contract.read_text(encoding="utf8"))
        if (m.get("source_pdf_sha256") != original_sha
            or clean(m.get("start_marker", "")) != clean(start_marker)
            or (next_marker is not None
                and clean(m.get("next_section_marker", "")) != clean(next_marker))
            or m.get("publication_allowed") is not False):
            raise SourceDiscoveryError("Manifest does not describe supplied source boundary")
    with fitz.open(source_pdf) as pdf:
        if not 1 <= len(pdf) <= 100:
            raise SourceDiscoveryError("PDF page count outside supported section range")
        # Require actual first / last page heading; no inference from neighboring PDFs.
        start_top, start_bottom = _heading_bound(pdf[0], start_marker, first=True)
        if next_marker is not None:
            end_top, end_bottom = _heading_bound(pdf[-1], next_marker, first=False)
        else:
            end_top, end_bottom = float(pdf[-1].rect.height), float(pdf[-1].rect.height)
        if len(pdf) == 1 and end_top <= start_bottom:
            raise SourceDiscoveryError("Section end precedes section start")
        page_count = len(pdf)
        passages = []
        excluded_by_geometry = 0
        excluded_furniture = 0
        for page_no, page in enumerate(pdf, 1):
            lower = start_bottom if page_no == 1 else 55.0
            blocks = page.get_text("blocks", sort=True)
            footer_tops = [float(b[1]) for b in blocks
                           if "copyright" in clean(normalized_passage(b[4])[:90])]
            footer_top = min(footer_tops) if footer_tops else float(page.rect.height)-15
            upper = min(end_top, footer_top) if page_no == len(pdf) else footer_top
            for block in blocks:
                x0, y0, x1, y1, raw, *extra = block
                if extra and extra[-1] != 0:
                    continue
                if y0 < lower - .01 or y1 > upper + .01:
                    excluded_by_geometry += 1
                    continue
                text = normalized_passage(raw)
                heading = bool(re.match(r"^(?:Example|Quick Quiz)\s+\d+", text, re.I))
                if ((len(text) < 65 or len(text.split()) < 10) and not heading
                    or "copyright" in clean(text[:45])
                    or "all rights reserved" in clean(text[:70])):
                    excluded_furniture += 1
                    continue
                rect = [round(float(n), 3) for n in (x0, y0, x1, y1)]
                text_sha = hashlib.sha256(text.encode("utf8")).hexdigest()
                ident = f"p{page_no:02d}_{len(passages)+1:03d}_{text_sha[:10]}"
                passages.append({
                    "passage_id": ident,
                    "source_page": page_no,
                    "source_bbox": rect,
                    "text": text,
                    "source_sha256": text_sha,
                    "word_count": len(text.split()),
                    "kind": ("figure_caption" if
                             re.match(r"^Figure\s+\d+[.\-]\d+", text, re.I)
                             else "passage"),
                    "figure_mentions": _figure_labels(text),
                    "source_literal_not_publication_copy": True,
                })
    if not passages:
        raise SourceDiscoveryError("No substantive PDF passage in bounded section")
    matched = []
    if m is not None:
        for topic in m.get("topics", []):
            ids = [p["passage_id"] for p in passages
                   if p["source_page"] == topic.get("source_page") and any(
                       clean(anchor) in clean(p["text"])
                       for anchor in topic.get("source_anchors", []))]
            matched.append({"topic_id": topic.get("topic_id"),
                            "source_page": topic.get("source_page"),
                            "source_passage_ids_with_anchor_overlap": ids})
    matched_ids = {ident for t in matched
                   for ident in t["source_passage_ids_with_anchor_overlap"]}
    report = {
        "schema_version": 1,
        "status": "PRIVATE_SOURCE_PASSAGE_DISCOVERY_NOT_ACADEMIC_CERTIFICATION",
        "source_pdf_sha256": original_sha,
        "source_page_count": page_count,
        "start_marker": start_marker,
        "next_section_marker": next_marker,
        "end_of_pdf": bool(end_of_pdf),
        "first_page_heading_y": round(start_top, 3),
        "last_page_next_heading_y": round(end_top, 3) if next_marker else None,
        "passage_count": len(passages),
        "passages": passages,
        "candidate_topics": [_draft_topic(p) for p in passages],
        "figure_label_mentions": sorted({label for p in passages
                                         for label in p["figure_mentions"]}),
        "excluded_geometric_blocks": excluded_by_geometry,
        "excluded_short_or_furniture_blocks": excluded_furniture,
        "declared_topic_anchor_overlaps": matched,
        "passages_without_declared_topic_anchor_overlap": [
            p["passage_id"] for p in passages if p["passage_id"] not in matched_ids],
        "passage_overlap_is_not_semantic_coverage": True,
        "source_topic_completeness_proven": False,
        "figure_panel_to_caption_semantics_proven": False,
        "independent_full_academic_certification": False,
        "formal_voice_authorized": False,
        "publication_allowed": False,
    }
    if sha_file(source_pdf) != original_sha:
        raise SourceDiscoveryError("PDF modified during discovery")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--start-marker", required=True)
    parser.add_argument("--next-marker")
    parser.add_argument("--end-of-pdf", action="store_true")
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--new-private-report", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = args.new_private_report
    if (destination.exists() or destination.is_symlink()
        or not destination.parent.is_dir()
        or any(part.casefold() == "my drive" for part in destination.parts)):
        raise SourceDiscoveryError("Fresh private report outside Drive required")
    report = discover_passages(
        args.source, args.start_marker, args.next_marker,
        end_of_pdf=args.end_of_pdf, contract=args.contract)
    # Create with exclusive open; never overwrite existing reports.
    with destination.open("x", encoding="utf8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)
    print(json.dumps({"passages": report["passage_count"],
                      "figure_mentions": report["figure_label_mentions"],
                      "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
