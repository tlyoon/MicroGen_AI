"""Source-bound offline QA screen; structural evidence only, never academic acceptance."""
from __future__ import annotations
import json
import re
from pathlib import Path

from PIL import Image
import pymupdf as fitz

from microgen_figure_composition import sha256
from microgen_vector_region_proposals import PROPOSAL_CODE_SHA256, PROPOSAL_DIR

QA_CODE_SHA256 = sha256(Path(__file__))
QA_RECEIPT = ("vector_qa_screen_unapproved_" +
              PROPOSAL_CODE_SHA256[:12] + "_" + QA_CODE_SHA256[:12] + ".json")
FORMAL = re.compile(r"^FIGURE\s+\d+\.\d+\b")


class VectorScreenError(ValueError):
    pass


def _ink_edge_counts(file: Path) -> dict:
    with Image.open(file) as source:
        image = source.convert("RGB")
        w, h = image.size
        if min(w, h) < 20:
            raise VectorScreenError("Candidate figure too small")
        def dark(x, y):
            return min(image.getpixel((x, y))) < 170
        return {
            "left": sum(dark(x, y) for x in range(3) for y in range(h)),
            "right": sum(dark(w - x - 1, y) for x in range(3) for y in range(h)),
            "top": sum(dark(x, y) for y in range(3) for x in range(w)),
            "bottom": sum(dark(x, h - y - 1) for y in range(3) for x in range(w)),
        }


def screen_vector_proposals(stage: Path) -> dict:
    stage = Path(stage).resolve(strict=True)
    source = stage / "source.pdf"
    before = sha256(source)
    bundle = stage / PROPOSAL_DIR
    try:
        manifest = json.loads((bundle / "proposal_receipt.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise VectorScreenError("No verifiable private vector proposals") from exc
    if (manifest.get("source_pdf_sha256") != before or
            manifest.get("proposer_code_sha256") != PROPOSAL_CODE_SHA256 or
            manifest.get("mapping_accepted") is not False or
            manifest.get("publication_allowed") is not False):
        raise VectorScreenError("Proposal source/code/safety invariant changed")
    findings = []
    with fitz.open(source) as document:
        for item in manifest["proposals"]:
            candidate = bundle / item["filename"]
            if sha256(candidate) != item["png_sha256"]:
                raise VectorScreenError("Proposed PNG has changed")
            page = document[item["page"] - 1]
            region = fitz.Rect(item["source_clip_bbox"])
            text_leakage = []
            caption_leakage = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line["spans"]).strip()
                    if FORMAL.match(text):
                        # PDF math fonts can report a caption-line bbox 5x
                        # taller than its visible glyphs. Recompute the
                        # visible formal label position independently of the
                        # geometry proposer; require an actual 3pt gap.
                        labels = [span for span in line["spans"]
                                  if FORMAL.match(span.get("text", "").strip())]
                        if len(labels) != 1:
                            raise VectorScreenError("Ambiguous caption-label span")
                        label_box = fitz.Rect(labels[0]["bbox"])
                        # A caption elsewhere on the same page is not
                        # an intrusion. Require spatial overlap of both
                        # horizontal bands and the caption's vertical zone.
                        near_label = (
                            region.x0 < label_box.x1 and
                            region.x1 > label_box.x0 and
                            region.y0 < label_box.y1 and
                            # Stored geometry is rounded to 0.01 pt;
                            # tolerate 0.05 pt only, not caption overlap.
                            region.y1 > label_box.y0 - 3 + 0.05
                        )
                        if near_label:
                            caption_leakage.append(text[:100])
                        continue
                    if len(text) > 75 and any(
                            fitz.Rect(span["bbox"]).intersects(region)
                            for span in line["spans"]):
                        text_leakage.append(text[:100])
            counts = _ink_edge_counts(candidate)
            flagged = bool(caption_leakage or text_leakage or
                           max(counts.values()) > 10)
            findings.append({
                "label": item["label"], "page": item["page"],
                "png_sha256": item["png_sha256"],
                "edge_ink_counts": counts,
                "caption_intrusion": caption_leakage,
                "long_text_intrusion": text_leakage,
                "boundary_review_required": flagged
            })
    if sha256(source) != before:
        raise VectorScreenError("Source PDF changed during QA")
    report = {
        "schema_version": 1, "source_pdf_sha256": before,
        "proposer_code_sha256": PROPOSAL_CODE_SHA256,
        "qa_code_sha256": QA_CODE_SHA256,
        "figures_screened": len(findings),
        "figures_flagged": [r["label"] for r in findings
                            if r["boundary_review_required"]],
        "findings": findings,
        "structural_screen_passed": not any(
            r["boundary_review_required"] for r in findings),
        "scientific_qa_accepted": False, "mapping_accepted": False,
        "publication_allowed": False, "provider_calls": 0,
    }
    dest = stage / QA_RECEIPT
    payload = json.dumps(report, indent=2)
    if dest.exists():
        if dest.read_text("utf-8") != payload:
            raise VectorScreenError("Existing source-bound QA receipt differs")
        return report
    with dest.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    return report
