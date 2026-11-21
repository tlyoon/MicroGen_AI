"""Offline, source-hashed vector figure evidence for safe mapper recovery.

Only diagnoses observed PDF/crop structure; never guesses an image-to-caption mapping.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
import pymupdf as fitz

from microgen_figure_composition import sha256

FORMAL = re.compile(r"^FIGURE\s+(\d+\.\d+)\b", re.I)

def inspect_vector_source(stage: Path) -> dict:
    stage = Path(stage).resolve(strict=True)
    pdf_file = stage / "source.pdf"
    before = sha256(pdf_file)
    pages = []
    labels = []
    with fitz.open(pdf_file) as doc:
        for page_no, page in enumerate(doc, 1):
            found = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    label = "".join(s.get("text", "") for s in line["spans"]).strip()
                    m = FORMAL.match(label)
                    if m:
                        found.append({"number": m.group(1), "caption_bbox": [round(x, 2) for x in line["bbox"]]})
                        labels.append(m.group(1))
            crops = sorted((stage / "pages" / f"page_{page_no}").glob("fig_*.png"))
            pages.append({"page": page_no, "embedded_raster_count": len(page.get_images(full=True)),
                          "vector_drawing_count": len(page.get_drawings()),
                          "crop_count": len(crops), "crop_sha256": {p.name: sha256(p) for p in crops},
                          "formal_captions": found})
    if sha256(pdf_file) != before:
        raise ValueError("Source changed during vector evidence collection")
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    # Preserve ambiguity in the diagnostic; a duplicate is never accepted as a mapping.
    return {"schema_version": 1, "source_pdf_sha256": before, "pages": pages,
            "duplicate_caption_numbers": repeated,
            "formal_caption_count": len(labels), "cropped_region_count": sum(x["crop_count"] for x in pages),
            "mapping_accepted": False, "publication_allowed": False,
            "gemini_invoked": False, "tts_invoked": False,
            "status": "VECTOR_SOURCE_EVIDENCE_ONLY_NOT_MAPPING_ACCEPTANCE"}

def record_vector_blocker(stage: Path) -> Path:
    stage = Path(stage).resolve(strict=True)
    receipt = inspect_vector_source(stage)
    # Evidence is diagnostic; never replace a previous evidence or mapping receipt.
    target = stage / "offline_vector_mapping_blocker.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    return target
