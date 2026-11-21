"""Read-only original-textbook source.pdf intake before lecture generation.

Source-file identity and extraction coverage are technical evidence only.
This stage never invokes Gemini, TTS, Whisper, publishing or a media render.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import pymupdf as fitz

from microgen_source_safe_orchestrator import atomic_json, digest
from microgen_figure_geometry_inventory import figure_region_inventory
from microgen_equation_geometry import equation_region_inventory


class SourcePDFIntakeError(ValueError):
    pass


FORMAL_FIGURE = re.compile(r"^FIGURE\s+(\d+\.\d+[a-z]?)\b")


def _formal_source_figure_labels(source: Path) -> list[dict]:
    """Find actual formal caption glyphs, not body references to figures.

    This is a technical inventory, never permission to accept the diagrams.
    """
    rows = []
    with fitz.open(source) as pdf:
        for page_no, page in enumerate(pdf, 1):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    content = "".join(s.get("text", "") for s in line["spans"]).strip()
                    match = FORMAL_FIGURE.match(content)
                    if not match:
                        continue
                    spans = [s for s in line["spans"]
                             if FORMAL_FIGURE.match(s.get("text", "").strip())]
                    if len(spans) != 1:
                        raise SourcePDFIntakeError("Ambiguous formal figure caption span")
                    rows.append({"label": match.group(1), "source_page": page_no})
    numbers = [item["label"] for item in rows]
    if len(set(numbers)) != len(numbers):
        raise SourcePDFIntakeError("Duplicate formal figure caption label")
    return rows


def _verified_vector_coverage(source_dir: Path, source_sha: str, formal: list[dict]):
    """Reconcile independently mapped vector figures or hold downstream slides."""
    mapping = source_dir / ".microgen_vector_source_mapping.json"
    if not mapping.exists():
        return None
    if mapping.is_symlink() or not mapping.is_file():
        raise SourcePDFIntakeError("Unsafe vector source map")
    from microgen_vector_technical_mapping import verify_vector_technical_mapping
    try:
        verified = verify_vector_technical_mapping(source_dir)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        raise SourcePDFIntakeError("Untrusted source-vector technical mapping") from exc
    if (not isinstance(verified, dict)
        or verified.get("source_pdf_sha256") != source_sha
        or verified.get("publication_allowed") is not False
        or verified.get("scientific_qa_accepted") is not False):
        raise SourcePDFIntakeError("Vector mapping cannot authorize slide intake")
    mapped = [{"label": x["label"], "source_page": x["source_page"]}
              for x in verified.get("figures", [])]
    if sorted(mapped, key=lambda x:(x["source_page"],x["label"])) != sorted(
            formal, key=lambda x:(x["source_page"],x["label"])):
        raise SourcePDFIntakeError("Formal captions and verified source mapping disagree")
    return {"figure_count": len(mapped), "receipt_sha256": digest(mapping)}


def inspect_source_pdf(source_dir: Path) -> dict:
    """Inspect an *original source.pdf*, without touching its parent tree."""
    root = Path(source_dir)
    if not root.is_dir() or root.is_symlink():
        raise SourcePDFIntakeError("Expected a real original source directory")
    file = root / "source.pdf"
    if not file.is_file() or file.is_symlink():
        raise SourcePDFIntakeError("Expected an unchanged regular source.pdf")
    size = file.stat().st_size
    if not 200 <= size <= 100 * 1024 * 1024:
        raise SourcePDFIntakeError("Source PDF is empty or above conservative safety limit")
    original = digest(file)
    pages = []
    try:
        with fitz.open(file) as book:
            if book.needs_pass or not 1 <= len(book) <= 512:
                raise SourcePDFIntakeError("Encrypted or unbounded source PDF")
            for position, page in enumerate(book, 1):
                rect = page.rect
                if (not 100 <= rect.width <= 3000 or
                        not 100 <= rect.height <= 3000):
                    raise SourcePDFIntakeError("Unexpected source page geometry")
                content = page.get_text("text")
                searchable = len(re.sub(r"\s+", "", content))
                pages.append({
                    "source_page": position,
                    "text_characters": searchable,
                    "text_extraction_available": searchable >= 30,
                    "raster_image_references": len(page.get_images(full=True)),
                    "page_width_pt": round(rect.width, 3),
                    "page_height_pt": round(rect.height, 3),
                    "figure_label_mentions": len(re.findall(
                        r"\b(?:figure|fig\.)\s*\d+(?:\.\d+)?", content, flags=re.I)),
                })
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError) as exc:
        raise SourcePDFIntakeError("Original PDF is not safely readable") from exc
    if digest(file) != original:
        raise SourcePDFIntakeError("Source PDF changed during inspection")
    readable = sum(x["text_extraction_available"] for x in pages)
    total = sum(x["text_characters"] for x in pages)
    text_ready = readable / len(pages) >= .7 and total >= 100
    return {
        "schema_version": 1,
        "source_dir": str(root.resolve(strict=True)),
        "source_pdf_sha256": original,
        "source_pdf_size_bytes": size,
        "page_count": len(pages),
        "searchable_page_count": readable,
        "searchable_text_characters": total,
        "source_text_readiness": (
            "SOURCE_TEXT_READY" if text_ready else
            "SOURCE_TEXT_EXTRACTION_REQUIRED"),
        "pages": pages,
        "textbook_semantics_verified": False,
        "generated_slides": False,
        "generated_audio": False,
        "generated_video": False,
        "source_files_modified": False,
        "publication_allowed": False,
    }


def create_intake_receipt(source_dir: Path, destination: Path) -> dict:
    """Audit real PDF figures/maths in a wholly independent, new directory."""
    if Path(source_dir).is_symlink():
        raise SourcePDFIntakeError("Symlinked source directory is not authorized")
    source = Path(source_dir).resolve(strict=True)
    dest = Path(destination).resolve(strict=False)
    if (destination.is_symlink() or dest.exists() or dest == source or
            dest.is_relative_to(source) or source.is_relative_to(dest)):
        raise SourcePDFIntakeError("Use a new output directory outside the source tree")
    summary = inspect_source_pdf(source)
    dest.mkdir(parents=True, exist_ok=False)
    try:
        figure_file = dest / "figure_geometry.json"
        math_file = dest / "equation_geometry.json"
        figures = figure_region_inventory(source / "source.pdf", figure_file)
        equations = equation_region_inventory(source / "source.pdf", math_file)
        fdata = json.loads(figure_file.read_text(encoding="utf8"))
        mdata = json.loads(math_file.read_text(encoding="utf8"))
        if (fdata.get("source_pdf_sha256") != summary["source_pdf_sha256"] or
                mdata.get("source_pdf_sha256") != summary["source_pdf_sha256"] or
                len(fdata.get("slides", [])) != summary["page_count"] or
                mdata.get("slide_count") != summary["page_count"] or
                digest(source / "source.pdf") != summary["source_pdf_sha256"]):
            raise SourcePDFIntakeError("Geometry and original source mismatch")
        formal = _formal_source_figure_labels(source / "source.pdf")
        vector = _verified_vector_coverage(
            source, summary["source_pdf_sha256"], formal)
        if digest(source / "source.pdf") != summary["source_pdf_sha256"]:
            raise SourcePDFIntakeError("Source PDF changed during caption reconciliation")
        summary.update({
            # The generic drawing detector is advisory and often misses
            # entirely vector-drawn textbook figures. Never equate it with
            # the true set of styled source FIGURE captions.
            "source_figure_candidates": figures["figure_candidates"],
            "formal_source_figure_captions": formal,
            "formal_source_figure_count": len(formal),
            "verified_private_vector_figure_count": (
                vector["figure_count"] if vector else 0),
            "private_vector_mapping_receipt_sha256": (
                vector["receipt_sha256"] if vector else None),
            "technical_figure_mapping_complete": (
                vector is not None if formal else None),
            "source_math_line_candidates": equations["regions"],
            "figure_evidence_sha256": digest(figure_file),
            "math_evidence_sha256": digest(math_file),
            "next_action": (
                "RESTORE_SEARCHABLE_PDF_TEXT" if
                summary["source_text_readiness"] == "SOURCE_TEXT_EXTRACTION_REQUIRED"
                else ("VERIFY_SOURCE_FIGURE_MAPPING_BEFORE_SLIDES"
                      if formal and vector is None
                      else "PROCEED_TO_GROUNDED_SLIDES_AND_NARRATION")),
            "source_math_correctness_verified": False,
            "figure_caption_semantics_verified": False,
            "narrated_element_sync_verified": False,
        })
        atomic_json(dest / "source_intake_receipt.json", summary)
        return summary
    except BaseException:
        shutil.rmtree(dest)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_directory", type=Path,
                        help="Original subchapter directory with source.pdf")
    parser.add_argument("new_external_report_folder", type=Path)
    args = parser.parse_args()
    r = create_intake_receipt(args.source_directory, args.new_external_report_folder)
    print(json.dumps({k: r[k] for k in (
        "page_count", "source_text_readiness", "source_figure_candidates",
        "source_math_line_candidates", "next_action", "publication_allowed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
