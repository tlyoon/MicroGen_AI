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
        summary.update({
            "source_figure_candidates": figures["figure_candidates"],
            "source_math_line_candidates": equations["regions"],
            "figure_evidence_sha256": digest(figure_file),
            "math_evidence_sha256": digest(math_file),
            "next_action": (
                "RESTORE_SEARCHABLE_PDF_TEXT" if
                summary["source_text_readiness"] == "SOURCE_TEXT_EXTRACTION_REQUIRED"
                else "PROCEED_TO_GROUNDED_SLIDES_AND_NARRATION"),
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
