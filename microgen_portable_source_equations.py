"""Source-vector mathematical equation regions for private portable lecture candidates.

Equations are copied as original PDF vector content, not retyped as ASCII text.
This proves source/crop identity, NOT that selected mathematics is conceptually correct.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
import pymupdf as fitz

class SourceEquationError(ValueError):
    pass

def crop_sha(page, rect):
    """Stable SHA of a source PDF raster at a fixed resolution, including dimensions."""
    pm = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect,
                         colorspace=fitz.csRGB, alpha=False)
    if not pm.width or not pm.height or min(pm.samples) > 230:
        raise SourceEquationError("Source equation crop has no visible content")
    return hashlib.sha256(
        f"{pm.width}x{pm.height}:".encode("ascii") + pm.samples
    ).hexdigest()

def checked_equations(source_pdf, manifest, narration, figure_slides):
    specs = manifest.get("source_equations", [])
    if not isinstance(specs, list) or len(specs) > len(narration["slides"]):
        raise SourceEquationError("Invalid mathematical source region inventory")
    found = {}
    for entry in specs:
        if not isinstance(entry, dict):
            raise SourceEquationError("Malformed source equation mapping")
        idx, src_page = entry.get("slide"), entry.get("source_page")
        coords, expected = entry.get("source_bbox"), entry.get("source_crop_sha256")
        if (type(idx) is not int or not 1 <= idx <= len(narration["slides"])
            or idx in found or idx in figure_slides
            or type(src_page) is not int or src_page != narration["slides"][idx-1]["source_page"]
            or not 1 <= src_page <= len(source_pdf)
            or not isinstance(coords, list) or len(coords) != 4
            or any(type(a) not in (int, float) or not -1e5 < a < 1e5 for a in coords)
            or not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected)):
            raise SourceEquationError("Ambiguous source equation geometry or provenance")
        rect = fitz.Rect(coords)
        page = source_pdf[src_page-1]
        if (not rect.is_valid or rect.is_empty or not page.rect.contains(rect)
            or not 15 <= rect.width <= page.rect.width
            or not 7 <= rect.height <= 180):
            raise SourceEquationError("Equation source box is outside a valid page region")
        # A mixed first page can still contain the PREVIOUS textbook section.
        if src_page == 1:
            start = manifest.get("start_marker")
            hits = page.search_for(start) if isinstance(start, str) and start else []
            if not hits or rect.y0 < max(hit.y1 for hit in hits):
                raise SourceEquationError("First-page equation is not proven below section start")
        actual = crop_sha(page, rect)
        if actual != expected:
            raise SourceEquationError("Original vector equation crop differs from expected hash")
        # Fail closed: the boundary page may include following-section mathematics.
        if (manifest.get("next_section_marker") is not None
            and src_page == len(source_pdf)):
            raise SourceEquationError("Equation on adjacent-section boundary page requires manual region isolation")
        found[idx] = {"source_page": src_page, "source_bbox": list(coords),
                      "source_crop_sha256": actual,
                      "original_pdf_vector_copied": True,
                      "mathematical_semantics_independently_verified": False}
    return found
