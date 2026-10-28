"""Source-bound raster similarity diagnostics for real textbook figure mappings.

This is *not* a semantic, mathematical or figure-to-speech release check.
Anomalies help target source extraction repairs; high scores never auto-approve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf as fitz
from microgen_source_safe_orchestrator import atomic_json, digest


class FigurePixelAuditError(ValueError):
    pass


def best_match(page_gray, figure_gray, scales=None):
    """Find strongest bounded normalized template score across safe rescalings."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise FigurePixelAuditError("opencv-python and numpy required for pixel audit") from exc
    if scales is None:
        scales = np.linspace(.35, 2.05, 33)
    if page_gray.ndim != 2 or figure_gray.ndim != 2:
        raise FigurePixelAuditError("Grayscale inputs required")
    if page_gray.size == 0 or figure_gray.size == 0 or figure_gray.std() < 2:
        raise FigurePixelAuditError("Blank or invalid source figure")
    best = (-1.0, None, None)
    for scale in scales:
        if not .15 <= float(scale) <= 3.0:
            raise FigurePixelAuditError("Unbounded comparison scale")
        width = round(figure_gray.shape[1] * float(scale))
        height = round(figure_gray.shape[0] * float(scale))
        if min(width, height) < 10 or width >= page_gray.shape[1] or height >= page_gray.shape[0]:
            continue
        template = cv2.resize(figure_gray, (width, height),
                              interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        if template.std() < 2:
            continue
        _, score, _, xy = cv2.minMaxLoc(cv2.matchTemplate(
            page_gray, template, cv2.TM_CCOEFF_NORMED))
        if score > best[0]:
            best = (float(score), float(scale), tuple(map(int, xy)))
    if best[1] is None:
        raise FigurePixelAuditError("No valid comparison at available raster scales")
    return best


def audit_source_figures(stage, figure_review, output):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise FigurePixelAuditError("opencv-python and numpy required") from exc
    s = Path(stage).resolve(strict=True)
    review = Path(figure_review).resolve(strict=True)
    dest = Path(output).absolute()
    if (dest.exists() or dest.is_symlink() or dest.is_relative_to(s) or
            s.is_relative_to(dest) or dest.is_relative_to(review) or
            review.is_relative_to(dest)):
        raise FigurePixelAuditError("Unused independent output folder required")
    receipt_path = review / "figure_coverage_receipt.json"
    pdf_path = s / "source.pdf"
    map_path = review / "figure_source_mapping.csv"
    for p in (receipt_path, pdf_path, map_path):
        if not p.is_file() or p.is_symlink():
            raise FigurePixelAuditError("Exact original PDF and review evidence required")
    receipt = json.loads(receipt_path.read_text(encoding="utf8"))
    if (receipt.get("source_pdf_sha256") != digest(pdf_path) or
            receipt.get("csv_sha256") != digest(map_path) or
            receipt.get("publication_allowed") is not False or
            receipt.get("figure_semantics_verified") is not False):
        raise FigurePixelAuditError("Source changed or unsafe prior approval")
    mapped = receipt.get("mapped_figures")
    if not isinstance(mapped, list) or not mapped or len(mapped) != receipt.get("mapped_count"):
        raise FigurePixelAuditError("Incomplete original figure map")
    original_hashes = {str(p): digest(p) for p in (receipt_path, pdf_path, map_path)}
    rows = []
    ids = set()
    with fitz.open(pdf_path) as book:
        for entry in mapped:
            figure_id = entry.get("figure")
            page = entry.get("source_page")
            filename = entry.get("filename")
            if (not isinstance(figure_id, str) or figure_id in ids or
                    type(page) is not int or not 1 <= page <= len(book) or
                    not isinstance(filename, str) or Path(filename).name != filename or
                    not re.fullmatch(r"(?i)figure\s*\d+\.\d+[a-z]?\.png", filename)):
                raise FigurePixelAuditError("Ambiguous figure identity or unsafe image filename")
            ids.add(figure_id)
            pic = review / "figures" / filename
            original = s / filename
            if (not pic.is_file() or pic.is_symlink() or
                    not original.is_file() or original.is_symlink() or
                    digest(pic) != entry.get("sha256") or
                    digest(original) != entry.get("sha256")):
                raise FigurePixelAuditError("Mapped source image changed")
            matrix = fitz.Matrix(1.4, 1.4)
            pix = book[page - 1].get_pixmap(matrix=matrix, alpha=False)
            src = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            src_gray = cv2.cvtColor(src[:, :, :3], cv2.COLOR_RGB2GRAY)
            fig_gray = cv2.imread(str(pic), cv2.IMREAD_GRAYSCALE)
            if fig_gray is None:
                raise FigurePixelAuditError("Cannot decode figure PNG")
            score, scale, xy = best_match(src_gray, fig_gray)
            rows.append({"figure": figure_id, "source_page": page,
                         "image_sha256": entry["sha256"], "match_score": round(score, 6),
                         "scale": round(scale, 6), "top_left": xy,
                         "diagnostic": ("LOW_PIXEL_MATCH_REVIEW_REQUIRED" if score < .65
                                        else "PIXEL_MATCH_CANDIDATE_NOT_SEMANTIC_PROOF")})
    if len(rows) != receipt.get("mapped_count") or any(digest(p) != h for p, h in original_hashes.items()):
        raise FigurePixelAuditError("Source changed during comparison")
    dest.mkdir(parents=True, exist_ok=False)
    try:
        result = {"scope": "SOURCE_PAGE_PIXEL_COMPARISON_ONLY", "mapped_count": len(rows),
                  "possible_low_matches": sum(r["match_score"] < .65 for r in rows),
                  "results": rows, "source_sha256": original_hashes,
                  "figure_semantics_verified": False,
                  "figure_narration_sync_verified": False, "publication_allowed": False}
        atomic_json(dest / "pixel_comparison_receipt.json", result)
        return result
    except Exception:
        import shutil
        shutil.rmtree(dest)
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True)
    p.add_argument("--review", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = audit_source_figures(a.stage, a.review, a.output)
    print(json.dumps({"mapped": result["mapped_count"], "possible_low_matches":
                      result["possible_low_matches"], "publication_allowed": False}))
