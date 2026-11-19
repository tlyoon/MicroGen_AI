"""Conservative automatic recovery of omitted *vector* textbook figures.

For a missing Figure X.Y.png in generated slides, this routine accepts only a
single distinctly styled, numbered caption in the immutable source PDF, a
compact same-column vector drawing adjacent immediately above that caption,
and all graphic labels inside a SHA-bound source crop. Ambiguity fails closed.

It never invents an illustration, overwrites an existing figure, performs
OCR, calls a generative model, or labels a crop scientifically certified.
The normal independent scientific, figure and visual QA still apply.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

import pymupdf

from microgen_source_safe_orchestrator import atomic_json

NAME = re.compile(r"Figure ([0-9]+)\.([0-9]+)([a-zA-Z]?)\.png\Z")
CAPTION = re.compile(r"(?i)^Figure\s+([0-9]+)\.([0-9]+)([a-zA-Z]?)\b")


class CaptionVectorRecoveryError(RuntimeError):
    """A source-bound graphic cannot be recovered without guessing."""


def digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _styled_caption(page, figure_label: str) -> list[dict]:
    found = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        lines = block.get("lines", [])
        if not lines:
            continue
        spans = lines[0].get("spans", [])
        if not spans:
            continue
        first = spans[0]
        match = CAPTION.match(first.get("text", "").strip())
        if not match:
            continue
        label = f"{int(match.group(1))}.{int(match.group(2))}{match.group(3).lower()}"
        if label != figure_label:
            continue
        # A blue bold caption is distinguishable from plain-body prose
        # beginning "Figure X.Y illustrates ...". Other source templates
        # may use other styles; abstain rather than guess.
        color = int(first.get("color", 0))
        red, green, blue = (color >> 16) & 255, (color >> 8) & 255, color & 255
        if ("bold" not in first.get("font", "").lower()
                or blue < red + 45 or blue < green + 25):
            continue
        found.append({"bbox": pymupdf.Rect(block["bbox"]),
                      "caption_font": first["font"],
                      "caption_color": color})
    return found


def _source_vector_geometry(page, caption: pymupdf.Rect) -> dict:
    width = page.rect.width
    if (caption.width < 45 or caption.width > width * 0.36
            or not (caption.x0 > page.rect.x0 + width * 0.60
                    or caption.x1 < page.rect.x0 + width * 0.40)):
        raise CaptionVectorRecoveryError(
            "Caption is not a narrow, isolated figure column")
    stripe = pymupdf.Rect(
        max(page.rect.x0, caption.x0 - 15),
        max(page.rect.y0, caption.y0 - 300),
        min(page.rect.x1, caption.x1 + 15),
        caption.y0 - 4,
    )
    drawings = []
    for graphic in page.get_drawings():
        box = pymupdf.Rect(graphic["rect"])
        if (box.is_empty or box.width < 5 or box.height < 2
                or box.get_area() < 70):
            continue
        within = box & stripe
        if (not within.is_empty
                and within.get_area() >= box.get_area() * 0.94):
            drawings.append(box)
    if len(drawings) < 3:
        raise CaptionVectorRecoveryError(
            "Insufficient source-vector evidence below uniquely styled caption")
    drawn_top = min(r.y0 for r in drawings)
    drawn_end = max(r.y1 for r in drawings)
    if (caption.y0 - drawn_end > 65
            or drawn_top <= stripe.y0 + 2
            or drawn_end >= caption.y0 - 3):
        raise CaptionVectorRecoveryError(
            "Graphic is separated from caption or collides with its text")

    # Include all label blocks belonging to the graphic; these may extend
    # 20-35 pt beyond the vector path bounds (axes, a/b keys, callouts).
    labels = []
    for item in page.get_text("blocks"):
        if len(item) < 7 or item[6] != 0:
            continue
        box = pymupdf.Rect(item[:4])
        if (box.is_empty or box.x0 < stripe.x0
                or box.x1 > stripe.x1 or box.y0 < drawn_top - 37
                or box.y1 > min(drawn_end + 24, caption.y0 - 2)):
            continue
        labels.append(box)
    if len(labels) < 3:
        raise CaptionVectorRecoveryError(
            "Source figure lacks enough independently extractable labels")
    all_boxes = drawings + labels
    clip = pymupdf.Rect(
        max(page.rect.x0, min(r.x0 for r in all_boxes) - 4),
        max(page.rect.y0, min(r.y0 for r in all_boxes) - 4),
        min(page.rect.x1, max(r.x1 for r in all_boxes) + 4),
        min(caption.y0 - 3, max(r.y1 for r in all_boxes) + 3),
    )
    if (clip.is_empty or clip.width < 65 or clip.height < 80
            or clip.width > width * 0.40
            or clip.height > page.rect.height * 0.44
            or clip.y1 >= caption.y0 - 2):
        raise CaptionVectorRecoveryError(
            "Unsafe or incomplete source figure/caption geometry")
    return {"crop_bbox": [round(float(v), 3) for v in clip],
            "caption_bbox": [round(float(v), 3) for v in caption],
            "vector_regions": len(drawings),
            "label_blocks": len(labels)}


def _identify(pdf, name: str) -> dict:
    match = NAME.fullmatch(name)
    if match is None:
        raise CaptionVectorRecoveryError("Expected source Figure X.Y.png")
    figure_label = (f"{int(match.group(1))}.{int(match.group(2))}"
                    f"{match.group(3).lower()}")
    matches = []
    for idx, page in enumerate(pdf):
        for record in _styled_caption(page, figure_label):
            matches.append((idx, record))
    if len(matches) != 1:
        raise CaptionVectorRecoveryError(
            "Expected one independently styled source figure caption, "
            f"found {len(matches)} for {figure_label}")
    index, record = matches[0]
    return {"name": name, "figure_label": figure_label,
            "source_page": index + 1,
            "caption_style": {
                "font": record["caption_font"],
                "color": record["caption_color"]},
            **_source_vector_geometry(pdf[index], record["bbox"])}


def _figure_references(stage: Path) -> list[str]:
    tex = stage / "slides.tex"
    if (not tex.is_file() or tex.is_symlink()
            or not (stage / "source.pdf").is_file()
            or (stage / "source.pdf").is_symlink()):
        raise CaptionVectorRecoveryError("Immutable source and slides.tex required")
    names = re.findall(
        r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}",
        tex.read_text(encoding="utf-8-sig"))
    if not names:
        raise CaptionVectorRecoveryError("No source figure referenced by TeX")
    if any(Path(name).name != name or ".." in name for name in names):
        raise CaptionVectorRecoveryError("Unsafe figure reference in slides.tex")
    return sorted(set(names), key=str.casefold)


def _reference_identity(stage: Path) -> str:
    """Source figure identity survives harmless TeX formatting/reflow changes."""
    refs = _figure_references(stage)
    return hashlib.sha256(json.dumps(refs, sort_keys=True).encode("utf-8")).hexdigest()


def _missing_files(stage: Path) -> list[str]:
    missing = [
        name for name in _figure_references(stage)
        if not (stage / name).is_file()
    ]
    if not 1 <= len(missing) <= 3:
        raise CaptionVectorRecoveryError("No eligible 1-3 missing figures")
    if any(NAME.fullmatch(n) is None for n in missing):
        raise CaptionVectorRecoveryError("Unrecognized missing figure name")
    return missing


def recover_caption_anchored_vectors(stage: Path) -> dict:
    """Automatically create only uniquely source-attested missing graphics.

    Preview all candidates and source hashes before writing any destination.
    Use exclusive create to guarantee an existing accepted figure is never
    overwritten. Every output can be reverified from immutable PDF geometry.
    """
    stage = Path(stage).resolve(strict=True)
    missing = _missing_files(stage)
    source = stage / "source.pdf"
    tex = stage / "slides.tex"
    source_sha = digest(source)
    tex_sha = digest(tex)
    refs_sha = _reference_identity(stage)
    with pymupdf.open(source) as pdf:
        selected = [_identify(pdf, name) for name in missing]
        previews = []
        for row in selected:
            page = pdf[row["source_page"] - 1]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8),
                                  clip=pymupdf.Rect(row["crop_bbox"]),
                                  alpha=False)
            if pix.width < 120 or pix.height < 120:
                raise CaptionVectorRecoveryError("Figure image is too small")
            previews.append((pix.tobytes("png"), [pix.width, pix.height]))
    if digest(source) != source_sha or digest(tex) != tex_sha:
        raise CaptionVectorRecoveryError("Source/TeX changed during figure attestation")
    created: list[Path] = []
    try:
        for row, (data, size) in zip(selected, previews):
            filename = stage / row["name"]
            # Exclusive create: never modify an existing source/accepted
            # image even during concurrent generator activity. Register
            # immediately after successful creation so partial writes are
            # removed on a later I/O failure.
            with filename.open("xb") as file:
                created.append(filename)
                file.write(data)
            row["output_sha256"] = digest(filename)
            row["pixel_size"] = size
        if (digest(source) != source_sha or digest(tex) != tex_sha
                or _reference_identity(stage) != refs_sha):
            raise CaptionVectorRecoveryError("Source/figure references changed during promotion")
        receipt = {
            "schema_version": 1,
            "status": "SOURCE_CAPTION_VECTOR_GEOMETRY_ATTESTED",
            "source_pdf_sha256": source_sha,
            "figure_refs_sha256": refs_sha,
            # Diagnostic only: frame normalization/reflow may legitimately
            # change the surrounding TeX without altering figure identity.
            "slides_tex_sha256_when_recovered": tex_sha,
            "source_image_identity": "unique styled caption with adjacent vector paths",
            "science_qa_required": True,
            "publication_allowed": False,
            "figures": selected,
        }
        atomic_json(stage / ".microgen_source_caption_vector_recovery.json", receipt)
        return {"status": receipt["status"], "figures": len(selected),
                "caption_vector_attested": True,
                "science_qa_required": True}
    except Exception:
        for created_path in created:
            created_path.unlink(missing_ok=True)
        raise


def validate_source_caption_vector_recovery(stage: Path) -> dict | None:
    """Reopen receipt and verify source, TeX, figure hashes and geometry."""
    stage = Path(stage)
    receipt = stage / ".microgen_source_caption_vector_recovery.json"
    if not receipt.is_file():
        return None
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if (data.get("schema_version") != 1
                or data.get("status") != "SOURCE_CAPTION_VECTOR_GEOMETRY_ATTESTED"
                or digest(stage / "source.pdf") != data["source_pdf_sha256"]
                or _reference_identity(stage) != data["figure_refs_sha256"]):
            raise CaptionVectorRecoveryError(
                "Source PDF or referenced figure identities differ")
        with pymupdf.open(stage / "source.pdf") as pdf:
            for row in data["figures"]:
                name = row["name"]
                if NAME.fullmatch(name) is None:
                    raise CaptionVectorRecoveryError("Unsafe receipt output filename")
                output = stage / name
                if (name not in _figure_references(stage)
                        or output.is_symlink()
                        or digest(output) != row["output_sha256"]):
                    raise CaptionVectorRecoveryError("Recovered PNG hash differs")
                expected = _identify(pdf, name)
                for key in ("crop_bbox", "caption_bbox", "source_page",
                            "vector_regions", "label_blocks"):
                    if row[key] != expected[key]:
                        raise CaptionVectorRecoveryError(
                            "Source caption/figure geometry attestation drift")
                page = pdf[row["source_page"] - 1]
                rendered = page.get_pixmap(
                    matrix=pymupdf.Matrix(1.8, 1.8),
                    clip=pymupdf.Rect(row["crop_bbox"]), alpha=False,
                )
                rerendered_hash = hashlib.sha256(
                    rendered.tobytes("png")).hexdigest()
                if (rerendered_hash != row["output_sha256"]
                        or [rendered.width, rendered.height] != row["pixel_size"]):
                    raise CaptionVectorRecoveryError(
                        "Recovered graphic is not the recorded source-PDF render")
        return {"receipt_sha256": digest(receipt),
                "figures": [row["name"] for row in data["figures"]]}
    except (KeyError, OSError, ValueError, TypeError, pymupdf.FileDataError) as exc:
        raise CaptionVectorRecoveryError(
            f"Source-caption recovery receipt invalid: {exc}") from exc
