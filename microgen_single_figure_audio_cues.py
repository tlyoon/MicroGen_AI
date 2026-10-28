"""Conservative real-WAV word-to-single-figure highlight candidates.

This augments existing source-bound WORD cues with image-box overlays when a
recognized "curve" or "graph" coincides with one image on the narrated slide.
No academic figure semantics, full element sync or pronunciation approval.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_source_safe_orchestrator import atomic_json, digest, read_json
from microgen_fresh_source_cues import source_inventory
from microgen_two_part_word_highlight import validate


class SingleFigureCueError(ValueError):
    pass


ANCHOR_WORDS = frozenset(("curve", "graph"))


def exact_stage_figure_asset(embedded: Image.Image, candidates):
    """Require one pixel-identical source-stage figure asset, not a random image."""
    pixel = embedded.convert("RGB")
    matches = [(name, sha) for name, sha, source in candidates
               if source.size == pixel.size and source.tobytes() == pixel.tobytes()]
    return matches[0] if len(matches) == 1 else None


def image_anchor_cues(words, narration, boxes, *, wav_seconds, page_rect):
    """Suggest time-bound image outlines; empty for ambiguous figure geometry."""
    if not isinstance(words, list) or not isinstance(narration, str):
        raise SingleFigureCueError("Source narration and word inventory required")
    if not isinstance(boxes, list):
        raise SingleFigureCueError("Image regions must be explicitly inventoried")
    if len(boxes) != 1:
        return []
    box = fitz.Rect(boxes[0])
    outer = fitz.Rect(page_rect)
    if (box.is_empty or not outer.contains(box) or
            box.width < 30 or box.height < 30 or
            box.get_area() > .85 * outer.get_area()):
        return []
    cues = []
    for word in words:
        if not isinstance(word, dict):
            raise SingleFigureCueError("Malformed ASR word")
        label = re.sub(r"[^a-z]", "", str(word.get("word", "")).lower())
        if label not in ANCHOR_WORDS:
            continue
        if not re.search(r"\b" + re.escape(label) + r"\b", narration, re.I):
            continue
        start, end, conf = (
            word.get("start"), word.get("end"), word.get("conf"))
        if (any(not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (start, end, conf)) or
                not 0 <= start < end <= wav_seconds + .02 or conf < .9):
            continue
        cues.append({
            "text": "UNVERIFIED_FIGURE_REFERENCE_" + label,
            "start": round(max(0., float(start) - .12), 3),
            "end": round(min(float(wav_seconds), float(end) + .45), 3),
            "confidence": round(float(conf), 4),
            "box": [float(v) for v in box],
            "cue_kind": "SINGLE_IMAGE_SPOKEN_WORD_CANDIDATE",
            "figure_semantics_verified": False,
        })
    return cues[:3]


def build_figure_cues(stage, original_word_report, asr_folder, new_folder):
    """Validate source PDF, each original WAV and each ASR input before output."""
    base, source, prior = validate(stage, original_word_report)
    dest = Path(new_folder).resolve(strict=False)
    asr = Path(asr_folder).resolve(strict=True)
    src_report = Path(original_word_report).resolve(strict=True)
    if (dest.exists() or dest.is_symlink() or dest == base or
            dest.is_relative_to(base) or base.is_relative_to(dest) or
            dest.is_relative_to(asr) or asr.is_relative_to(dest) or
            dest.is_relative_to(src_report.parent)):
        raise SingleFigureCueError("New separate report folder required")
    if not asr.is_dir() or asr.is_symlink():
        raise SingleFigureCueError("Real independent ASR inventory required")
    pdf_sha = digest(base / "slides.pdf")
    narration_sha = digest(base / "script_tts.json")
    prior_sha = digest(src_report)
    candidate_rows = []
    reports = json.loads(json.dumps(prior))
    asr_hashes = {}
    asset_hashes = {}
    stage_figure_assets = []
    for asset in sorted(base.glob("*.png")):
        if not re.fullmatch(r"(?i)figure\s*\d+\.\d+[a-z]?\.png", asset.name):
            continue
        if asset.is_symlink() or asset.stat().st_size > 20 * 1024 * 1024:
            raise SingleFigureCueError("Unsafe source figure asset")
        with Image.open(asset) as pic:
            stage_figure_assets.append((asset.name, digest(asset), pic.convert("RGB")))
    source_script = read_json(base / "script_tts.json")["slides"]
    if len(source_script) != source["slide_count"]:
        raise SingleFigureCueError("Original narration inventory changed")
    with fitz.open(base / "slides.pdf") as book:
        if len(book) != source["slide_count"]:
            raise SingleFigureCueError("Current PDF/WAV page count mismatch")
        for idx, (page, slide) in enumerate(zip(book, reports["slides"]), 1):
            asr_file = asr / f"slide{idx:02d}.json"
            if not asr_file.is_file() or asr_file.is_symlink():
                raise SingleFigureCueError("Incomplete independent recognition")
            observed = read_json(asr_file)
            expected_sha = source["wav_inventory"][idx-1]["wav_sha256"]
            if (observed.get("slide") != idx or
                    observed.get("wav_sha256") != expected_sha or
                    observed.get("publication_allowed") is not False):
                raise SingleFigureCueError("ASR slide/WAV identity mismatch")
            recognition = observed.get("recognition")
            if (not isinstance(recognition, dict) or
                    recognition.get("source_wav_sha256") != expected_sha or
                    recognition.get("phonetic_identity_verified") is not False or
                    recognition.get("semantic_word_alignment_certified") is not False):
                raise SingleFigureCueError("Untrusted phonetic/semantic claims")
            boxes = []
            images = page.get_images(full=True)
            for image in images:
                for box in page.get_image_rects(image[0]):
                    region = [round(v, 3) for v in box]
                    if region not in boxes:
                        boxes.append(region)
            verified_asset = None
            if len(images) == 1 and len(boxes) == 1:
                with Image.open(io.BytesIO(book.extract_image(images[0][0])["image"])) as embedded:
                    verified_asset = exact_stage_figure_asset(embedded, stage_figure_assets)
            cues = image_anchor_cues(
                recognition.get("words"), source_script[idx-1]["tts_text"],
                boxes if verified_asset else [],
                wav_seconds=source["wav_inventory"][idx-1]["duration_seconds"],
                page_rect=page.rect)
            slide["cues"].extend(cues)
            slide["cues"].sort(key=lambda c: c["start"])
            if cues:
                asset_hashes[verified_asset[0]] = verified_asset[1]
                candidate_rows.append({"slide": idx, "cues": cues,
                    "exact_embedded_source_asset": verified_asset[0],
                    "exact_embedded_source_asset_sha256": verified_asset[1],
                    "source_stage_asset_pixels_identical": True,
                    "original_wav_sha256":expected_sha,
                    "original_asr_file_sha256":digest(asr_file),
                    "semantic_approval":False})
            asr_hashes[asr_file.name] = digest(asr_file)
    reports["total_cues"] = sum(len(row["cues"]) for row in reports["slides"])
    if (digest(base / "slides.pdf") != pdf_sha or
            digest(base / "script_tts.json") != narration_sha or
            digest(src_report) != prior_sha or source_inventory(base)[1] != source or
            any(digest(base / name) != sha for name, sha in asset_hashes.items()) or
            any(digest(asr / name) != sha for name, sha in asr_hashes.items())):
        raise SingleFigureCueError("Source, cues or ASR changed during inspection")
    dest.mkdir(parents=True, exist_ok=False)
    try:
        augmented = dest / "figure_augmented_word_cues.json"
        atomic_json(augmented, reports)
        # The ordinary source-bound renderer MUST accept the augmented input.
        validate(base, augmented)
        receipt = {"schema_version":1,
            "status":"SPOKEN_SINGLE_IMAGE_ANCHOR_CANDIDATES_NOT_SEMANTIC_PROOF",
            "source":source,"base_cue_report_sha256":prior_sha,
            "augmented_cue_report_sha256":digest(augmented),
            "source_pdf_sha256":pdf_sha,"asr_file_sha256":asr_hashes,
            "figure_asset_sha256":asset_hashes,
            "source_stage_figure_pixels_identical":bool(candidate_rows),
            "candidate_slide_count":len(candidate_rows),
            "figure_anchor_cue_count":sum(len(row["cues"]) for row in candidate_rows),
            "candidate_slides":candidate_rows,
            "figure_semantics_verified":False,
            "full_element_timing_verified":False,
            "word_phonetics_verified":False,
            "publication_allowed":False}
        atomic_json(dest / "figure_anchor_cue_receipt.json", receipt)
        return receipt
    except Exception:
        shutil.rmtree(dest)
        raise


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True)
    p.add_argument("--original-cues",required=True)
    p.add_argument("--asr",required=True)
    p.add_argument("--new-output",required=True)
    a=p.parse_args()
    r=build_figure_cues(a.stage,a.original_cues,a.asr,a.new_output)
    print(json.dumps({"candidate_slides":r["candidate_slide_count"],
        "figure_anchor_cues":r["figure_anchor_cue_count"],
        "publication_allowed":False}))
