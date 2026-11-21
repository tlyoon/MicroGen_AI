"""Source-pixel-verified offline vector figure composition; academic QA remains mandatory.

Runs only in the explicitly bounded offline mapping path. Supports idempotent
commit and a partially promoted prior transaction without overwriting user data.
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageChops

from microgen_figure_composition import FigureCollector, sha256, validate_figure_receipt
from microgen_vector_region_proposals import PROPOSAL_DIR, PROPOSAL_CODE_SHA256
from microgen_vector_proposal_qa import QA_RECEIPT, QA_CODE_SHA256, screen_vector_proposals

RECEIPT_NAME = ".microgen_vector_source_mapping.json"
STAGING = "vector_technical_mapping_private_" + PROPOSAL_CODE_SHA256[:12]


class VectorMappingError(ValueError):
    pass


def _safe_source(stage: Path):
    original = stage / "source.pdf"
    if (not original.is_file() or original.is_symlink()
            or not (stage / PROPOSAL_DIR / "proposal_receipt.json").is_file()):
        raise VectorMappingError("Immutable original PDF and proposed geometry required")
    return original, sha256(original)


def _receipt(stage: Path, source_sha: str):
    proposals = json.loads((stage / PROPOSAL_DIR / "proposal_receipt.json").read_text("utf-8"))
    qa = screen_vector_proposals(stage)
    if (proposals.get("source_pdf_sha256") != source_sha
        or proposals.get("proposer_code_sha256") != PROPOSAL_CODE_SHA256
        or proposals.get("mapping_accepted") is not False
        or proposals.get("scientific_qa_accepted") is not False
        or proposals.get("publication_allowed") is not False
        or proposals.get("blocked") != []
        or qa.get("structural_screen_passed") is not True
        or qa.get("figures_flagged") != []
        or qa.get("mapping_accepted") is not False
        or qa.get("publication_allowed") is not False
        or len(proposals.get("proposals", [])) != proposals.get("formal_caption_count")
        or not proposals.get("proposals")):
        raise VectorMappingError("Unaccepted source-vector figure evidence; no mapping")
    labels = [item.get("label") for item in proposals["proposals"]]
    if len(labels) != len(set(labels)):
        raise VectorMappingError("Duplicate figure labels")
    return proposals, qa


def _verify_source_pixels(pdf: fitz.Document, item: dict, candidate: Path):
    label = item["label"]
    page = item["page"] - 1
    if (not isinstance(label, str) or not label.replace(".", "").isdigit()
        or type(page) is not int or not 0 <= page < len(pdf)
        or item["filename"] != f"Figure {label}.png"
        or candidate.is_symlink()
        or not candidate.is_file()
        or sha256(candidate) != item["png_sha256"]):
        raise VectorMappingError("Invalid source figure identity or changed candidate")
    bounds = fitz.Rect(item["source_clip_bbox"])
    if (bounds.is_empty or not pdf[page].rect.contains(bounds)
        or bounds.y1 > item["caption_bbox"][1] - 2.9):
        raise VectorMappingError("Proposed source crop intersects formal caption")
    pix = pdf[page].get_pixmap(matrix=fitz.Matrix(2, 2), clip=bounds, alpha=False)
    with Image.open(candidate) as picture:
        original = picture.convert("RGB")
        raster = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if original.size != raster.size or ImageChops.difference(original, raster).getbbox():
            raise VectorMappingError("Proposed graphic pixels do not match source PDF")


def _verify_promoted(stage: Path, rows: list[dict], source_sha: str) -> dict:
    record_path = stage / RECEIPT_NAME
    if not record_path.is_file() or record_path.is_symlink():
        raise VectorMappingError("Incomplete vector mapping promotion")
    data = json.loads(record_path.read_text("utf-8"))
    if (data.get("schema_version") != 1
        or data.get("source_pdf_sha256") != source_sha
        or data.get("proposer_code_sha256") != PROPOSAL_CODE_SHA256
        or data.get("qa_code_sha256") != QA_CODE_SHA256
        or data.get("qa_receipt_sha256") != sha256(stage / QA_RECEIPT)
        or data.get("source_geometry_mapping_verified") is not True
        or data.get("scientific_qa_accepted") is not False
        or data.get("publication_allowed") is not False
        or data.get("figure_count") != len(rows)
        or data.get("figures") != rows):
        raise VectorMappingError("Untrusted published technical geometry receipt")
    composed = validate_figure_receipt(stage)
    figures = {x["destination"]: x for x in composed["figures"]}
    if len(figures) != len(rows):
        raise VectorMappingError("Technical figures omitted from composition")
    for row in rows:
        figure = figures.get(row["destination"])
        image = stage / row["destination"]
        if (not figure or not image.is_file() or image.is_symlink()
                or sha256(image) != row["composed_sha256"]
                or figure["source_page"] != f"page_{row['source_page']}"
                or figure["output_sha256"] != row["composed_sha256"]):
            raise VectorMappingError("Source-figure composition provenance diverged")
    return data


def verify_vector_technical_mapping(stage: Path) -> dict | None:
    stage = Path(stage)
    record = stage / RECEIPT_NAME
    if not record.exists():
        return None
    source, source_sha = _safe_source(stage)
    proposals, _ = _receipt(stage, source_sha)
    pending = []
    with fitz.open(source) as pdf:
        for item in proposals["proposals"]:
            candidate = stage / PROPOSAL_DIR / item["filename"]
            _verify_source_pixels(pdf, item, candidate)
            composed = stage / item["filename"]
            if not composed.is_file():
                raise VectorMappingError("Missing composed graphic")
            pending.append({
                "label": item["label"], "source_page": item["page"],
                "destination": item["filename"], "source_clip_bbox": item["source_clip_bbox"],
                "source_png_sha256": item["png_sha256"],
                "composed_sha256": sha256(composed)})
    return _verify_promoted(stage, pending, source_sha)


def promote_vector_technical_mapping(stage: Path) -> dict:
    stage = Path(stage).resolve(strict=True)
    source, source_sha = _safe_source(stage)
    proposals, qa = _receipt(stage, source_sha)
    if (stage / RECEIPT_NAME).exists():
        return verify_vector_technical_mapping(stage)
    staging = stage / STAGING
    if staging.is_symlink():
        raise VectorMappingError("Unsafe staging path")
    if not staging.exists():
        staging.mkdir()
        # Source-pixel verification comes *before* any mapped figure is staged.
        with fitz.open(source) as pdf:
            for item in proposals["proposals"]:
                _verify_source_pixels(pdf, item,
                                      stage / PROPOSAL_DIR / item["filename"])
        collector = FigureCollector(staging)
        for item in proposals["proposals"]:
            collector.add(staging / item["filename"],
                          stage / PROPOSAL_DIR / item["filename"],
                          source_page=f"page_{item['page']}")
        collector.finalize()
        validate_figure_receipt(staging)
    else:
        validate_figure_receipt(staging)
    mapping = validate_figure_receipt(staging)
    by_name = {x["destination"]: x for x in mapping["figures"]}
    rows = []
    for item in proposals["proposals"]:
        name = item["filename"]
        crop = stage / PROPOSAL_DIR / name
        if (name not in by_name
            or by_name[name]["source_page"] != f"page_{item['page']}"
            or by_name[name]["source_crops"][0]["sha256"] != sha256(crop)):
            raise VectorMappingError("Staging composition diverged from original source")
        rows.append({
            "label": item["label"], "source_page": item["page"],
            "destination": name, "source_clip_bbox": item["source_clip_bbox"],
            "source_png_sha256": item["png_sha256"],
            "composed_sha256": by_name[name]["output_sha256"]
        })
    if len(rows) != len(mapping["figures"]):
        raise VectorMappingError("Extra or missing staged figure")
    if sha256(source) != source_sha:
        raise VectorMappingError("Source PDF changed before private promotion")
    for row in rows:
        name = row["destination"]
        dst = stage / name
        staged = staging / name
        if dst.exists() or dst.is_symlink():
            if not dst.is_file() or dst.is_symlink() or sha256(dst) != row["composed_sha256"]:
                raise VectorMappingError("Existing figure is different: " + name)
            continue
        tmp = stage / (name + ".vector-tmp")
        if tmp.exists() or tmp.is_symlink():
            if not tmp.is_file() or tmp.is_symlink() or sha256(tmp) != row["composed_sha256"]:
                raise VectorMappingError("Unreconciled partially-written figure")
        else:
            with staged.open("rb") as inp, tmp.open("xb") as out:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
        tmp.replace(dst)
    root_composition = stage / "figure_composition_receipt.json"
    staged_composition = staging / "figure_composition_receipt.json"
    if root_composition.exists() or root_composition.is_symlink():
        if not root_composition.is_file() or root_composition.is_symlink() or sha256(root_composition) != sha256(staged_composition):
            raise VectorMappingError("Conflicting previous composition receipt")
    else:
        shutil.copyfile(staged_composition, root_composition)
    validate_figure_receipt(stage)
    data = {
        "schema_version": 1, "source_pdf_sha256": source_sha,
        "proposer_code_sha256": PROPOSAL_CODE_SHA256,
        "qa_code_sha256": QA_CODE_SHA256,
        "qa_receipt_sha256": sha256(stage / QA_RECEIPT),
        "source_geometry_mapping_verified": True,
        "scientific_qa_accepted": False,
        "publication_allowed": False, "provider_calls": 0,
        "figure_count": len(rows), "figures": rows,
    }
    with (stage / RECEIPT_NAME).open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
    return verify_vector_technical_mapping(stage)
