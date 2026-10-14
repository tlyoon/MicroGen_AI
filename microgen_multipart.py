"""Source-grounded, duration-checked multipart output for MicroGen_AI.

Produces coherent *slide-boundary* parts from an explicitly validated scene
manifest. It never cuts an equation or a slide mid-utterance, and refuses an
unsourced plan. A manuscript/scene review remains necessary for teaching QA.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path

from microgen_quality import QualityError, check_video, sha256

PARTS_SCHEMA = 1
MIN_REASONABLE_SECONDS = 20.0


class MultipartError(QualityError):
    pass


def wav_seconds(path: Path) -> float:
    import wave
    with wave.open(str(path), "rb") as stream:
        secs = stream.getnframes() / stream.getframerate()
    if not math.isfinite(secs) or secs <= 0:
        raise MultipartError(f"Invalid WAV duration: {path}")
    return secs


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _manifest_path(stage: Path) -> Path:
    return stage / "lesson_scenes.json"


def validate_scenes(stage: Path, *, durations: list[float] | None = None) -> tuple[list[dict], list[float]]:
    """Every scene must have contiguous real slide IDs and nonempty source evidence."""
    stage = Path(stage)
    manifest = _manifest_path(stage)
    if not manifest.is_file():
        raise MultipartError(
            "A source-grounded lesson_scenes.json is required for multipart mode. "
            "Run microgen_scene_proposal.py and review its proposal first."
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != PARTS_SCHEMA:
        raise MultipartError("Unknown multipart scene manifest version")
    if data.get("reviewed") is not True or not str(data.get("reviewer") or "").strip():
        raise MultipartError("Scene citations and concept boundaries require reviewer approval")
    if data.get("source_sha256") != sha256(stage / "source.pdf"):
        raise MultipartError("Source PDF changed since lesson scenes were approved")
    if data.get("slides_sha256") != sha256(stage / "slides.pdf"):
        raise MultipartError("Slide deck changed since lesson scenes were approved")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise MultipartError("Manifest must contain source-grounded scenes")
    if durations is None:
        count = sum(len(s.get("slides", [])) for s in scenes)
        durations = [wav_seconds(stage / f"slide{i}.wav") for i in range(1, count + 1)]
    if not durations:
        raise MultipartError("Missing measured WAV durations")
    # Validate the cited source page(s) are within the real source document.
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    with fitz.open(stage / "source.pdf") as source:
        source_count = source.page_count
    with fitz.open(stage / "slides.pdf") as pdf:
        page_count = pdf.page_count
    expected = list(range(1, page_count + 1))
    supplied: list[int] = []
    for scene in scenes:
        ids = scene.get("slides", [])
        if not ids or any(not isinstance(i, int) or isinstance(i, bool) for i in ids):
            raise MultipartError("Every scene must contain integer slide numbers")
        if ids != list(range(ids[0], ids[0] + len(ids))):
            raise MultipartError(f"Scene slides must be consecutive: {ids}")
        pages = scene.get("source_pages")
        if not isinstance(pages, list) or not pages or any(
            not isinstance(p, int) or isinstance(p, bool) or p < 1 or p > source_count
            for p in pages
        ):
            raise MultipartError(f"Missing or invalid source-page citations for scene {ids[0]}")
        if not isinstance(scene.get("topic"), str) or not scene["topic"].strip():
            raise MultipartError("Every scene requires a meaningful topic name")
        if not isinstance(scene.get("natural_break_after"), bool):
            raise MultipartError("Every scene must mark its natural boundary explicitly")
        supplied.extend(ids)
    if supplied != expected or len(durations) != page_count:
        raise MultipartError(f"Scene inventory mismatch: expected 1..{page_count}, got {supplied}")
    if any(not math.isfinite(v) or v <= 0 for v in durations):
        raise MultipartError("WAV durations must be positive and finite")
    return scenes, durations


def plan_parts(
    scenes: list[dict], durations: list[float], *, target_seconds: float = 510,
    max_seconds: float = 570, min_seconds: float = 240,
) -> list[dict]:
    """Dynamic program: only concept boundaries are cut candidates."""
    if not 0 < min_seconds < target_seconds <= max_seconds < 600:
        raise MultipartError("Invalid part timing policy")
    total_slides = sum(len(s["slides"]) for s in scenes)
    if len(durations) != total_slides:
        raise MultipartError("Slide/audio count mismatch")
    totals = [sum(durations[i - 1] for i in s["slides"]) for s in scenes]
    n = len(scenes)
    prefix = [0.0]
    for dur in totals:
        prefix.append(prefix[-1] + dur)
    scores = [float("inf")] * (n + 1)
    parent = [-1] * (n + 1)
    scores[0] = 0.0
    for b in range(1, n + 1):
        for a in range(b - 1, -1, -1):
            elapsed = prefix[b] - prefix[a]
            if elapsed > max_seconds + 0.001:
                break
            if a > 0 and not scenes[a - 1]["natural_break_after"]:
                continue
            if not math.isfinite(scores[a]):
                continue
            # Discourage very short videos but do not artificially lengthen audio.
            penalty = ((elapsed - target_seconds) / target_seconds) ** 2
            if elapsed < min_seconds:
                penalty += ((min_seconds - elapsed) / min_seconds) ** 2 * 8
            score = scores[a] + 0.5 + penalty
            if score < scores[b]:
                scores[b] = score
                parent[b] = a
    if parent[n] < 0:
        raise MultipartError(
            "Cannot reach the video duration ceiling without cutting an "
            "indivisible concept. Subdivide that scene and regenerate the "
            "source-grounded lesson plan."
        )
    intervals = []
    i = n
    while i:
        a = parent[i]
        intervals.append((a, i))
        i = a
    intervals.reverse()
    result = []
    for idx, (a, b) in enumerate(intervals, 1):
        slides = [num for s in scenes[a:b] for num in s["slides"]]
        result.append({
            "part": idx, "slides": slides,
            "topic_start": scenes[a]["topic"],
            "topic_end": scenes[b-1]["topic"],
            "source_pages": sorted(set(page for s in scenes[a:b] for page in s["source_pages"])),
            "duration_seconds": round(prefix[b] - prefix[a], 3),
            "boundary_verified": b == n or scenes[b - 1]["natural_break_after"],
        })
    if [x for p in result for x in p["slides"]] != list(range(1, total_slides + 1)):
        raise MultipartError("Multipart plan omitted, reordered or duplicated slides")
    return result


def render_parts(
    stage: Path, segments: list[Path], concat, *, target_seconds: float = 510,
    max_seconds: float = 570,
) -> dict:
    """Check source and segment evidence; publish part files last, with receipt."""
    stage = Path(stage)
    durations = [wav_seconds(stage / f"slide{i}.wav") for i in range(1, len(segments)+1)]
    scenes, checked = validate_scenes(stage, durations=durations)
    parts = plan_parts(scenes, checked, target_seconds=target_seconds,
                       max_seconds=max_seconds)
    for segment in segments:
        check_video(segment)
    hashes = {
        "source_sha256": sha256(stage / "source.pdf"),
        "slides_sha256": sha256(stage / "slides.pdf"),
        "manifest_sha256": sha256(_manifest_path(stage)),
        "segment_sha256": [sha256(x) for x in segments],
    }
    outputs = []
    for part in parts:
        path = stage / f"slides_part_{part['part']:02d}.mp4"
        candidate = stage / f"slides_part_{part['part']:02d}.candidate.mp4"
        involved = [segments[i-1] for i in part["slides"]]
        sig = hashlib.sha256(_canonical({
            "parts_schema": PARTS_SCHEMA, "hashes": hashes,
            "part": part, "target": target_seconds, "max": max_seconds
        }).encode("utf-8")).hexdigest()
        receipt_file = stage / f".microgen_part_{part['part']:02d}.json"
        reused = False
        if path.is_file() and receipt_file.is_file():
            try:
                old = json.loads(receipt_file.read_text(encoding="utf-8"))
                if old.get("cache_key") == sig and old.get("sha256") == sha256(path):
                    check_video(path, expected_seconds=part["duration_seconds"])
                    reused = True
            except (OSError, ValueError, QualityError):
                reused = False
        if not reused:
            candidate.unlink(missing_ok=True)
            concat(involved, candidate)
            actual = check_video(candidate, expected_seconds=part["duration_seconds"])
            if actual["seconds"] >= 600:
                raise MultipartError("Rendered part exceeds the 10-minute safety ceiling")
            if path.is_file():
                backup = stage / f"slides_part_{part['part']:02d}.before-{sha256(path)[:12]}.mp4"
                if not backup.exists():
                    shutil.copy2(path, backup)
            os.replace(candidate, path)
            stamp = {"cache_key": sig, "sha256": sha256(path)}
            temp = receipt_file.with_suffix(".json.tmp")
            temp.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
            os.replace(temp, receipt_file)
        part["mp4_sha256"] = sha256(path)
        part["file"] = path.name
        part["actual_duration_seconds"] = check_video(path)["seconds"]
        outputs.append(part)
    receipt = {
        "schema_version": PARTS_SCHEMA,
        "validation": "source-referenced scenes and contiguous validated media",
        "input_hashes": hashes,
        "parts": outputs,
    }
    tmp = stage / ".microgen_multipart_receipt.tmp"
    tmp.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(tmp, stage / ".microgen_multipart_receipt.json")
    return receipt
