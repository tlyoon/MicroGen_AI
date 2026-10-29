"""Conservative no-network figure mapping from original PDF image identities.

Refuse to guess ambiguous captions or crop mappings. Currently supports a
single formally captioned 2-panel (a/b) figure on one source page. A source-
matching candidate is not an academic approval of figure meaning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from io import BytesIO
from pathlib import Path

import pymupdf as fitz

from microgen_figure_composition import FigureCollector, sha256, validate_figure_receipt
from microgen_batch import source_page_extraction_valid


class OfflineFigureMapError(ValueError):
    pass


def qualified_panel_matches(scores: list[list[int]], *, min_good: int = 35,
                            min_ratio: float = 4.0) -> list[int]:
    """Find a one-to-one crop-to-original-image mapping or fail closed."""
    if (len(scores) != 2 or any(len(row) != 2 for row in scores) or
            any(type(score) is not int or score < 0 for row in scores
                for score in row)):
        raise OfflineFigureMapError("Only two trustworthy image scores are supported")
    assignment = []
    for row in scores:
        best = max(range(2), key=lambda j: row[j])
        second = row[1 - best]
        if row[best] < min_good or row[best] < min_ratio * (second + 1):
            raise OfflineFigureMapError("Image crop mapping is ambiguous")
        assignment.append(best)
    if sorted(assignment) != [0, 1]:
        raise OfflineFigureMapError("Two crops mapped to the same PDF image")
    return assignment


def orb_matches(crop: Path, original: bytes) -> int:
    """Positive visual image-feature matches; never use filename order alone."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise OfflineFigureMapError("Local OpenCV is required; do not use a model fallback") from exc
    a = cv2.imdecode(np.frombuffer(original, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(str(crop), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None or min(*a.shape, *b.shape) < 35:
        return 0
    orb = cv2.ORB_create(nfeatures=1000)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None:
        return 0
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    return sum(1 for pair in matches if len(pair) == 2
               and pair[0].distance < 0.75 * pair[1].distance)


def _source_text_lines(page):
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            raw = "".join(span.get("text", "") for span in line["spans"]).strip()
            if raw:
                yield raw, fitz.Rect(line["bbox"])


def source_caption_and_panels(page, image_rectangles):
    lines = list(_source_text_lines(page))
    captions = [(s, b) for s, b in lines
                if re.match(r"(?i)^figure\s+\d+\.\d+[a-z]?\b", s)]
    if len(captions) != 1:
        raise OfflineFigureMapError("Exactly one formal numbered figure caption required")
    caption, region = captions[0]
    m = re.match(r"(?i)^figure\s+(\d+\.\d+)\b", caption)
    number = m.group(1)
    if len(image_rectangles) != 2:
        raise OfflineFigureMapError("Exactly two source-image regions required")
    if not region.y0 >= max(x.y1 for x in image_rectangles):
        raise OfflineFigureMapError("Figure caption must follow both images on the same page")
    if not all(re.search(r"(?i)\(" + letter + r"\)", page.get_text("text"))
               for letter in ("a", "b")):
        raise OfflineFigureMapError("Formal caption must describe panels (a) and (b)")
    # A/b labels must independently occur just below their respective source
    # image rectangles, rather than assigning crop order speculatively.
    ordered = []
    for letter in ("a", "b"):
        possible = [idx for idx, box in enumerate(image_rectangles)
                    if any(s.lower() == letter
                           and label.x0 >= box.x0 - 6
                           and label.x1 <= box.x1 + 6
                           and 0 <= label.y0 - box.y1 <= 17
                           for s, label in lines)]
        if len(possible) != 1:
            raise OfflineFigureMapError("Panel label not spatially bound to source image")
        ordered.append(possible[0])
    if sorted(ordered) != [0, 1]:
        raise OfflineFigureMapError("Panel labels have conflicting geometry")
    return number, ordered


def map_source_figures(stage: Path) -> dict:
    """Map only fully provable images, leaving all user-owned inputs unchanged."""
    folder = Path(stage).resolve(strict=True)
    if not source_page_extraction_valid(folder):
        raise OfflineFigureMapError("Incomplete original source/Docling evidence")
    pages_root = folder / "pages"
    if ((pages_root / "figure_composition_receipt.json").exists() or
            (folder / "figure_composition_receipt.json").exists()):
        raise OfflineFigureMapError("Existing mapped evidence must not be overwritten")
    extraction = json.loads((folder / "figure_extraction_receipt.json").read_text("utf-8"))
    source_sha = sha256(folder / "source.pdf")
    crop_pages = []
    with fitz.open(folder / "source.pdf") as pdf:
        if len(pdf) != extraction["page_count"]:
            raise OfflineFigureMapError("Source page count changed")
        for n, page in enumerate(pdf, 1):
            crops = sorted((pages_root / f"page_{n}").glob("fig_*.png"))
            images = page.get_images(full=True)
            if crops or images:
                if not (len(crops) == len(images) == 2):
                    raise OfflineFigureMapError("Unexpected unmatched source images/crops")
                crop_pages.append((n, crops, page.number))
        if len(crop_pages) != 1:
            raise OfflineFigureMapError("Expected one source page with exactly two crops")
        n, crops, page_number = crop_pages[0]
        page = pdf[page_number]
        image_entries = page.get_images(full=True)
        image_data = [pdf.extract_image(item[0])["image"] for item in image_entries]
        boxes = []
        for entry in image_entries:
            rects = page.get_image_rects(entry[0])
            if len(rects) != 1:
                raise OfflineFigureMapError("Source image appears in multiple locations")
            boxes.append(rects[0])
        fig_number, label_to_image = source_caption_and_panels(page, boxes)
        scores = [[orb_matches(crop, img) for img in image_data] for crop in crops]
        crop_to_image = qualified_panel_matches(scores)
        image_to_crop = {image: crop_idx for crop_idx, image in enumerate(crop_to_image)}
        selected = [crops[image_to_crop[idx]] for idx in label_to_image]
        selected_hashes = [sha256(file) for file in selected]
        if sha256(folder / "source.pdf") != source_sha:
            raise OfflineFigureMapError("Original staged PDF changed during comparison")
        collector = FigureCollector(pages_root)
        for file in selected:
            collector.add(pages_root / f"Figure {fig_number}.png", file,
                          source_page=f"page_{n}")
        result = collector.finalize()
    # FigureCollector writes under pages; original mapper moves the image to
    # the stage root. Verify copy first, never overwrite a different image.
    picture = pages_root / f"Figure {fig_number}.png"
    final = folder / picture.name
    if final.exists() or final.is_symlink():
        raise OfflineFigureMapError("Unexpected existing final figure")
    shutil.copy2(picture, final)
    shutil.copy2(pages_root / "figure_composition_receipt.json",
                 folder / "figure_composition_receipt.json")
    validate_figure_receipt(folder)
    receipt = {
        "schema_version": 1,
        "status": "HIGH_CONFIDENCE_SOURCE_IMAGE_MAPPING_NOT_ACADEMIC_APPROVAL",
        "source_pdf_sha256": source_sha,
        "extraction_receipt_sha256": sha256(folder / "figure_extraction_receipt.json"),
        "page": n,
        "figure_label": f"Figure {fig_number}",
        "source_panel_labels": ["a", "b"],
        "panel_source_crop_names": [x.name for x in selected],
        "panel_crop_sha256": selected_hashes,
        "crop_original_image_good_match_scores": scores,
        "source_image_order": label_to_image,
        "composed_image_sha256": sha256(final),
        "figure_composition_sha256": sha256(folder / "figure_composition_receipt.json"),
        "figure_semantics_verified": False,
        "composite_academic_quality_verified": False,
        "gemini_invoked": False,
        "tts_invoked": False,
        "publication_allowed": False,
    }
    report_file = folder / "offline_figure_mapping_receipt.json"
    with report_file.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    return receipt


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--stage", type=Path, default=Path("."))
    args = cli.parse_args()
    result = map_source_figures(args.stage)
    print(json.dumps({"status": result["status"], "figure_label": result["figure_label"],
                      "gemini_invoked": False, "publication_allowed": False}))
