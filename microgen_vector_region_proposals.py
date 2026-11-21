"""Private, source-attested proposals for vector-drawn textbook figures.

Never promotes a proposal to a figure mapping or publication receipt.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_figure_composition import sha256

# Code-fingerprint private output so revised geometry never reuses old crops.
PROPOSAL_CODE_SHA256 = sha256(Path(__file__))
PROPOSAL_DIR = "vector_figure_candidates_unapproved_" + PROPOSAL_CODE_SHA256[:12]
FORMAL_CAPTION = re.compile(r"^FIGURE\s+(\d+\.\d+)\b")


class VectorProposalError(ValueError):
    pass


def _right_edge_ink(path: Path) -> int:
    with Image.open(path) as source:
        image = source.convert('RGB')
        width, height = image.size
        return sum(min(image.getpixel((width - 1 - x, y))) < 170
                   for x in range(min(width, 3)) for y in range(height))


def _edge_ink(path: Path, edge: str) -> int:
    with Image.open(path) as source:
        image = source.convert("RGB")
        w, h = image.size
        if min(w, h) < 20:
            raise VectorProposalError("Proposed source region too small")
        def dark(x, y):
            return min(image.getpixel((x, y))) < 170
        if edge == "left":
            return sum(dark(x, y) for x in range(3) for y in range(h))
        if edge == "bottom":
            return sum(dark(x, h - 1 - y) for y in range(3) for x in range(w))
        raise VectorProposalError("Unknown candidate edge")


def _caption_lines(page):
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            content = "".join(s.get("text", "") for s in line["spans"]).strip()
            m = FORMAL_CAPTION.match(content)
            if m:
                # Use the visibly rendered formal FIGURE label's own bbox.
                # Whole-line bounds can be huge due to mathematical glyphs
                # such as fractions, falsely clipping graph axis labels.
                label_spans = [s for s in line["spans"]
                               if FORMAL_CAPTION.match(s.get("text", "").strip())]
                if len(label_spans) != 1:
                    raise VectorProposalError("Ambiguous formal caption label span")
                yield m.group(1), fitz.Rect(label_spans[0]["bbox"])


def _anchors_and_rules(page):
    anchors, rules = [], []
    for item in page.get_drawings():
        color = item.get("color")
        if color is None:
            continue
        box = fitz.Rect(item["rect"])
        if box.width > page.rect.width * .4 and box.height < 2:
            rules.append(box)
            continue
        if max(box.width, box.height) < 10:
            continue
        if max(color) - min(color) <= .28 or max(color) <= .55:
            continue
        anchors.append(box)
    return anchors, rules


def propose_regions(stage: Path) -> dict:
    """Make all high-visibility color-geometry candidates; never assign academic acceptance."""
    stage = Path(stage).resolve(strict=True)
    source = stage / "source.pdf"
    before = sha256(source)
    final = stage / PROPOSAL_DIR
    pending = stage / ("." + PROPOSAL_DIR + ".pending")
    if pending.exists() or pending.is_symlink():
        raise VectorProposalError("Interrupted vector proposal transaction requires reconciliation")
    previous = None
    if final.exists() or final.is_symlink():
        try:
            previous = json.loads((final / "proposal_receipt.json").read_text("utf-8"))
            if previous["source_pdf_sha256"] != before:
                raise VectorProposalError("Stale vector proposal source mismatch")
            for item in previous["proposals"]:
                if sha256(final / item["filename"]) != item["png_sha256"]:
                    raise VectorProposalError("Previously proposed figure changed")
            return previous
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise VectorProposalError("Unverifiable prior vector proposal directory") from exc
    pending.mkdir()
    proposals = []
    blocked = []
    labels = set()
    try:
        with fitz.open(source) as document:
            for page_no, page in enumerate(document, 1):
                captions = list(_caption_lines(page))
                anchors, separators = _anchors_and_rules(page)
                width = page.rect.width
                for label, caption in captions:
                    if label in labels:
                        raise VectorProposalError("Duplicate formal figure caption; ambiguous source")
                    labels.add(label)
                    left = caption.x0 < width * .31
                    x0, x1 = ((width*.02, width*.31) if left
                              else (width*.31, width*.97))
                    previous_bottom = max(
                        (c.y1 for _, c in captions
                         if (c.x0 < width*.31) == left and c.y1 < caption.y0),
                        default=0.0)
                    eligible = [
                        box for box in anchors
                        if x0 <= (box.x0+box.x1)/2 <= x1
                        and box.y0 < caption.y0 - 3
                        and box.y1 >= previous_bottom + 5
                    ]
                    groups = []
                    for box in sorted(eligible, key=lambda x: x.y0):
                        if groups and box.y0 - max(r.y1 for r in groups[-1]) <= 85:
                            groups[-1].append(box)
                        else:
                            groups.append([box])
                    if not groups:
                        blocked.append({"label": label, "page": page_no, "reason": "NO_COLOR_ANCHOR"})
                        continue
                    group = groups[-1]
                    # Numeric extrema also work for zero-height horizontal paths.
                    min_x = min(r.x0 for r in group)
                    max_x = max(r.x1 for r in group)
                    min_y = min(r.y0 for r in group)
                    max_y = max(r.y1 for r in group)
                    top = min_y - 38
                    near_rules = [r for r in separators
                                  if min_y-75 < r.y1 < min_y]
                    if near_rules:
                        top = max(top, max(r.y1 for r in near_rules)+6)
                    # Side-column axis labels can extend beyond caption band.
                    # Expand only around verified colored strokes, never into
                    # the adjacent main text column.
                    right = (min(width*.35, max_x+25) if left
                             else min(x1, max_x+35))
                    clip = fitz.Rect(max(x0, min_x-35),
                                     max(previous_bottom+3, top),
                                     right,
                                     min(caption.y0-3, max_y+33))
                    if (clip.width < 40 or clip.height < 25
                            or max_y > caption.y0 + 5
                            or caption.y0-max_y > 125):
                        blocked.append({"label": label, "page": page_no, "reason": "UNSAFE_GEOMETRY"})
                        continue
                    filename = f"Figure {label}.png"
                    candidate = pending / filename
                    page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip,
                                    alpha=False).save(str(candidate))
                    # Only widen a sidebar figure when its right edge shows
                    # actual touching ink. Keep the original if the bounded
                    # alternative does not improve the edge measurement.
                    if left and _right_edge_ink(candidate) > 10:
                        alternative = fitz.Rect(clip)
                        alternative.x1 = min(width * .35, max_x + 40)
                        if alternative.x1 > clip.x1 + 1:
                            proposed = pending / (filename + ".candidate.png")
                            page.get_pixmap(matrix=fitz.Matrix(2, 2),
                                            clip=alternative, alpha=False).save(str(proposed))
                            if _right_edge_ink(proposed) < _right_edge_ink(candidate):
                                proposed.replace(candidate)
                                clip = alternative
                            else:
                                proposed.unlink()
                    # Restore drawing endpoints when ink touches the *left*
                    # edge of a right-column candidate. Stay inside its
                    # caption column and accept the change only if measured
                    # edge contact falls (never expand blindly).
                    if not left and _edge_ink(candidate, "left") > 10:
                        alternative = fitz.Rect(clip)
                        alternative.x0 = max(width*.31, clip.x0-24)
                        if alternative.x0 < clip.x0 - 1:
                            temp = pending / (filename + ".left-candidate.png")
                            page.get_pixmap(matrix=fitz.Matrix(2, 2),
                                            clip=alternative, alpha=False).save(str(temp))
                            if _edge_ink(temp, "left") < _edge_ink(candidate, "left"):
                                temp.replace(candidate)
                                clip = alternative
                            else:
                                temp.unlink()
                    # Some axes and panel-letter glyphs extend beneath the
                    # colored curve. The *actual* FIGURE-label span provides
                    # a safe lower boundary even when equation fonts inflate
                    # the entire caption line's reported rectangle.
                    if _edge_ink(candidate, "bottom") > 10:
                        alternative = fitz.Rect(clip)
                        alternative.y1 = min(caption.y0-3, clip.y1+22)
                        if alternative.y1 > clip.y1 + 1:
                            temp = pending / (filename + ".bottom-candidate.png")
                            page.get_pixmap(matrix=fitz.Matrix(2, 2),
                                            clip=alternative, alpha=False).save(str(temp))
                            if _edge_ink(temp, "bottom") < _edge_ink(candidate, "bottom"):
                                temp.replace(candidate)
                                clip = alternative
                            else:
                                temp.unlink()
                    proposals.append({
                        "label": label, "page": page_no, "filename": filename,
                        "caption_bbox": [round(v, 2) for v in caption],
                        "source_clip_bbox": [round(v, 2) for v in clip],
                        "source_colored_drawings": len(group),
                        "png_sha256": sha256(candidate),
                        "status": "SOURCE_GEOMETRY_PROPOSAL_UNAPPROVED"
                    })
        if sha256(source) != before:
            raise VectorProposalError("Original source PDF changed during vector proposal")
        report = {
            "schema_version": 1, "source_pdf_sha256": before,
            "proposer_code_sha256": PROPOSAL_CODE_SHA256,
            "formal_caption_count": len(labels),
            "proposals": sorted(proposals, key=lambda x: (x["page"], x["label"])),
            "blocked": blocked, "mapping_accepted": False,
            "scientific_qa_accepted": False, "publication_allowed": False,
            "gemini_invoked": False, "tts_invoked": False
        }
        (pending / "proposal_receipt.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        pending.rename(final)
        return report
    except Exception:
        # Retain interrupted staging for explicit reconciliation; never
        # silently overwrite a partial prior transaction.
        raise
