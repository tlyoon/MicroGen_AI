#!/usr/bin/env python3
"""Repair legacy Beamer counters in isolated output; never publish media.

Compile twice to resolve Beamer's total-frame-number macro. For known overflow, apply
explicit, narrowly scoped frame shrink (max 10%), then compare original and
candidate PDF content, images and geometry before marking it as a valid candidate.
This cannot by itself reissue a hash-bound lecture completion receipt or fix MP4.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import microgen_quality as quality


class LegacyRepairError(RuntimeError):
    pass


FRAME_START = re.compile(r"\\begin\{frame\}(?:\[([^\]]+)\])?")
GRAPHIC = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
HEADER = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")


def sha(path: Path) -> str:
    return quality.sha256(path)


def patch_specific_frames(tex: str, frames: set[int], shrink: int) -> str:
    if not 1 <= shrink <= 10:
        raise LegacyRepairError("Frame shrink must be between 1 and 10 percent")
    occurrences = list(FRAME_START.finditer(tex))
    if not occurrences or any(n < 1 or n > len(occurrences) for n in frames):
        raise LegacyRepairError("Requested frame outside explicit Beamer frame list")
    for match in reversed(occurrences):
        index = occurrences.index(match) + 1
        if index in frames:
            if match.group(1) is not None:
                raise LegacyRepairError(f"Frame {index} already has options; manual review required")
            tex = tex[:match.start()] + rf"\begin{{frame}}[shrink={shrink}]" + tex[match.end():]
    return tex


def source_images(src: Path, tex: str, output: Path) -> list[str]:
    refs = GRAPHIC.findall(tex)
    for name in set(refs):
        source = src / name
        if not source.is_file() and not Path(name).suffix:
            source = next((src / (name + ext) for ext in (".png", ".jpg", ".jpeg", ".pdf")
                           if (src / (name + ext)).is_file()), source)
        if not source.is_file():
            raise LegacyRepairError(f"Missing source figure: {name}")
        target = output / source.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha(source) != sha(target):
            raise LegacyRepairError(f"Figure copy mismatch: {name}")
    for item in src.iterdir():
        if item.is_file() and item.suffix.lower() in (".sty", ".cls", ".png", ".jpg", ".jpeg", ".eps"):
            target = output / item.name
            if not target.exists():
                shutil.copy2(item, target)
    return refs


def pdf_observation(path: Path) -> list[dict]:
    import pymupdf
    result = []
    with pymupdf.open(path) as doc:
        for page_index, page in enumerate(doc, 1):
            header_regions = []
            for block in page.get_text("blocks"):
                if block[1] < 100 and HEADER.fullmatch(" ".join(block[4].split())):
                    header_regions.append(pymupdf.Rect(block[:4]))
            body_words = []
            for word in page.get_text("words"):
                word_rect = pymupdf.Rect(word[:4])
                if not any(r.intersects(word_rect) for r in header_regions):
                    body_words.append(word[4])
            images = []
            for im in page.get_images(full=True):
                image = doc.extract_image(im[0])
                images.append(hashlib.sha256(image["image"]).hexdigest())
            out_of_bounds = []
            boundary = page.rect + (-2, -2, 2, 2)
            for block in page.get_text("blocks"):
                rect = pymupdf.Rect(block[:4])
                if not rect.is_empty and rect.get_area() >= 12 and not boundary.contains(rect):
                    out_of_bounds.append([round(k, 2) for k in rect])
            result.append({
                "page": page_index, "words": body_words, "images": sorted(images),
                "rect": [round(page.rect.width, 3), round(page.rect.height, 3)],
                "out_of_bounds": out_of_bounds,
            })
    return result


def compare_pages(original: Path, candidate: Path) -> dict:
    source = pdf_observation(original)
    rendered = pdf_observation(candidate)
    if len(source) != len(rendered):
        raise LegacyRepairError("PDF page count differs after recompilation")
    additional_words: dict[str, list[str]] = {}
    for old, new in zip(source, rendered):
        page = old["page"]
        if old["images"] != new["images"]:
            raise LegacyRepairError(f"Embedded image content differs on page {page}")
        if old["rect"] != new["rect"]:
            raise LegacyRepairError(f"Page geometry differs on page {page}")
        missing = list((Counter(old["words"]) - Counter(new["words"])).elements())
        if missing:
            raise LegacyRepairError(f"Original PDF words disappeared on page {page}: {missing[:12]}")
        added = list((Counter(new["words"]) - Counter(old["words"])).elements())
        if added:
            additional_words[str(page)] = added
    return {
        "pages": len(source),
        "original_overflow_pages": [x["page"] for x in source if x["out_of_bounds"]],
        "candidate_overflow_pages": [x["page"] for x in rendered if x["out_of_bounds"]],
        "original_visible_words_preserved": True,
        "embedded_images_identical": True,
        "page_sizes_identical": True,
        "additional_visible_words": additional_words,
    }


def compile_twice(folder: Path, timeout: int) -> None:
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
           "-no-shell-escape", "-file-line-error", "slides.tex"]
    for n in (1, 2):
        try:
            run = subprocess.run(cmd, cwd=folder, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace", timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LegacyRepairError(f"pdflatex pass {n} failure: {exc}") from exc
        (folder / f"pdflatex_pass_{n}.log").write_text(run.stdout, encoding="utf-8")
        if run.returncode:
            raise LegacyRepairError(
                f"pdflatex pass {n} exit {run.returncode}: {run.stdout[-600:]}"
            )
        if not (folder / "slides.pdf").is_file():
            raise LegacyRepairError(f"No PDF after pass {n}")


def repair(source: Path, output: Path, *, shrink_frames: set[int] | None = None,
           shrink_percent: int = 5, timeout: int = 180) -> dict:
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise LegacyRepairError("Output already exists; will not overwrite")
    if source in output.parents or output in source.parents or source == output:
        raise LegacyRepairError("Output must not be inside source or source inside output")
    if {x.casefold() for x in output.parts} & {"my drive", "google drive", "onedrive", "dropbox"}:
        raise LegacyRepairError("Use an independent LOCAL scratch/output directory")
    if not source.is_dir() or not (source / "slides.tex").is_file():
        raise LegacyRepairError("Missing source slides.tex")
    original = source / "slides.pdf"
    quality.require_file(original)
    tex = (source / "slides.tex").read_text(encoding="utf-8-sig")
    import pymupdf
    with pymupdf.open(original) as doc:
        page_count = doc.page_count
    if shrink_frames:
        starts = FRAME_START.findall(tex)
        if len(starts) != page_count:
            raise LegacyRepairError("Ambiguous frame-to-page mapping; no shrink allowed")
        tex = patch_specific_frames(tex, shrink_frames, shrink_percent)
    tracked = [source / n for n in ("slides.tex", "slides.pdf", "slides.mp4", "source.pdf")
               if (source / n).is_file()]
    before = {p.name: sha(p) for p in tracked}
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".legacy-repair-", dir=output.parent))
    result = {
        "source": str(source), "output": str(output), "original_sha256": before,
        "shrink_frames": sorted(shrink_frames or []), "shrink_percent": shrink_percent,
        "publication_allowed": False, "academic_review_claimed": False,
        "code_scope": "isolated PDF candidate only; video/audio not regenerated",
    }
    try:
        (stage / "slides.tex").write_text(tex, encoding="utf-8")
        refs = source_images(source, tex, stage)
        compile_twice(stage, timeout)
        comparison = compare_pages(original, stage / "slides.pdf")
        result.update(comparison)
        result["referenced_graphics"] = len(refs)
        strict = quality.check_slide_pdf(stage / "slides.pdf", require_footer=True)
        result["validated_page_count"] = strict["pages"]
        result["new_pdf_sha256"] = sha(stage / "slides.pdf")
        if {p.name: sha(p) for p in tracked} != before:
            raise LegacyRepairError("Input changed while generating candidate")
        result["source_artifacts_unchanged"] = True
        result["status"] = "TECHNICAL_PDF_CANDIDATE_PASS"
        (stage / "repair_report.json").write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        stage.rename(output)
    except Exception:
        # Keep evidence in a separate failed-run scratch directory for diagnosis;
        # no candidate folder is published and nothing is copied to the source.
        error = stage / "FAILED_UNVERIFIED.txt"
        error.write_text("This output failed technical checks and is not a release candidate.\n",
                         encoding="utf-8")
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shrink-frames", default="",
                        help="Explicit slide indexes, e.g. 5,9; no automatic speculative shrink")
    parser.add_argument("--shrink-percent", type=int, default=5)
    args = parser.parse_args()
    nums = {int(x.strip()) for x in args.shrink_frames.split(",") if x.strip()}
    report = repair(args.source, args.output, shrink_frames=nums,
                    shrink_percent=args.shrink_percent)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
