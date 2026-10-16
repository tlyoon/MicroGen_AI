#!/usr/bin/env python3
"""Isolated, fail-closed visual repair of legacy Thomas lecture MP4s.

Recover original slide boundaries from actual video pixels (not WAV estimates),
prove each scene matches the corresponding OLD slide, render the corrected
slide PDF at those boundaries, and stream-copy the OLD AAC track. Neither
production files nor verified-completion receipts are altered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import microgen_quality as quality
from microgen_legacy_pdf_repair import compare_pages
from gen_video_v22 import ffmpeg_executable


class VideoRepairError(RuntimeError):
    pass


def run_ffmpeg(arguments: list[str], *, timeout: int = 240) -> subprocess.CompletedProcess:
    exe = ffmpeg_executable()
    if not exe:
        raise VideoRepairError("ffmpeg unavailable")
    try:
        p = subprocess.run([exe, "-nostdin", "-hide_banner", *arguments],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoRepairError(f"ffmpeg timed out or cannot launch: {exc}") from exc
    if p.returncode:
        raise VideoRepairError("ffmpeg error: " + p.stderr[-900:])
    return p


def media_duration(path: Path) -> float:
    exe = ffmpeg_executable()
    if not exe:
        raise VideoRepairError("ffmpeg unavailable")
    try:
        p = subprocess.run([exe, "-nostdin", "-hide_banner", "-i", str(path)],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, errors="replace", timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoRepairError(f"Cannot inspect media: {exc}") from exc
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    if not m:
        raise VideoRepairError(f"MP4 duration unavailable: {p.stderr[-400:]}")
    if "Video:" not in p.stderr or "Audio:" not in p.stderr:
        raise VideoRepairError("Old MP4 must contain both audio and video")
    return 3600 * int(m.group(1)) + 60 * int(m.group(2)) + float(m.group(3))


def parse_scene_pts(stderr: str, expected_pages: int, total_seconds: float) -> list[float]:
    pts = [float(v) for v in re.findall(r"pts_time:\s*([0-9.]+)", stderr)]
    if len(pts) != expected_pages - 1:
        raise VideoRepairError(
            f"Expected {expected_pages-1} identifiable slide changes, found {len(pts)}"
        )
    previous = 0.0
    for t in [*pts, total_seconds]:
        if not (math.isfinite(t) and t - previous >= 0.35):
            raise VideoRepairError("Slide timings invalid, ambiguous or too short")
        previous = t
    return pts


def detect_scene_times(old_mp4: Path, expected_pages: int, seconds: float,
                       sample_rate: int = 5) -> list[float]:
    # Decode at 5 Hz (precision +/-0.2s) and detect substantial static-slide
    # changes. Fail closed if animation or editing causes extra transitions.
    p = run_ffmpeg([
        "-loglevel", "info", "-i", str(old_mp4),
        "-vf", f"fps={sample_rate},scale=320:180,select='gt(scene,0.05)',showinfo",
        "-an", "-f", "null", "-"
    ], timeout=180)
    return parse_scene_pts(p.stderr, expected_pages, seconds)


def scene_midpoints(breaks: list[float], total: float) -> list[int]:
    boundaries = [0.0, *breaks, total]
    mids = [int((a+b)/2.0) for a, b in zip(boundaries, boundaries[1:])]
    if any(not (a < midpoint < b) for midpoint, (a, b) in
           zip(mids, zip(boundaries, boundaries[1:]))):
        raise VideoRepairError("Cannot sample a stable interior frame for each slide")
    if len(set(mids)) != len(mids):
        raise VideoRepairError("Overlapping slide sampling points")
    return mids


def _pdf_preview(pdf: Path, index: int, size=(640, 360)):
    import pymupdf
    from PIL import Image

    with pymupdf.open(pdf) as doc:
        page = doc[index]
        zoom = size[0] / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img.thumbnail(size)
    background = Image.new("RGB", size, "white")
    background.paste(img, ((size[0]-img.width)//2, (size[1]-img.height)//2))
    return background


def _distance(a, b) -> float:
    from PIL import ImageChops, ImageStat
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3.0


def validate_visual_mapping(old_mp4: Path, old_pdf: Path, breakpoints: list[float],
                            total: float, stage: Path, *, max_distance: float = 11.0) -> list[dict]:
    from PIL import Image
    times = scene_midpoints(breakpoints, total)
    # Input fps=1 indexes are actual seconds; select only the interior time of
    # each detected scene. Extract all snapshots in a single decode pass.
    expr = "+".join(f"eq(n\\,{t})" for t in times)
    folder = stage / "video_samples"
    folder.mkdir()
    run_ffmpeg([
        "-loglevel", "error", "-i", str(old_mp4),
        "-vf", "fps=1,select='" + expr + "',scale=640:360",
        "-vsync", "0", "-frames:v", str(len(times)),
        str(folder / "sample_%03d.png")
    ], timeout=180)
    samples = sorted(folder.glob("sample_*.png"))
    if len(samples) != len(times):
        raise VideoRepairError("Original video snapshots missing")
    reference = [_pdf_preview(old_pdf, i) for i in range(len(times))]
    result = []
    for i, (frame, sec) in enumerate(zip(samples, times)):
        with Image.open(frame) as img:
            snap = img.convert("RGB")
            all_distances = [_distance(snap, ref) for ref in reference]
        best = min(range(len(reference)), key=lambda n: all_distances[n])
        expected_distance = all_distances[i]
        record = {
            "scene": i+1, "timestamp_second": sec, "matching_pdf_page": best+1,
            "expected_mean_absolute_pixel_difference": round(expected_distance, 3),
            "second_best_distance": round(sorted(all_distances)[1], 3)
        }
        result.append(record)
        if best != i or expected_distance > max_distance:
            raise VideoRepairError(
                f"Original MP4 scene {i+1} does not match source slide {i+1}: {record}"
            )
    return result


def audio_stream_hash(video: Path) -> str:
    p = run_ffmpeg([
        "-loglevel", "error", "-i", str(video),
        "-map", "0:a:0", "-c:a", "copy", "-f", "hash", "-hash", "SHA256", "-"
    ], timeout=90)
    match = re.fullmatch(r"SHA256=([0-9a-fA-F]{64})\s*", p.stdout)
    if not match:
        raise VideoRepairError("Cannot hash AAC stream")
    return match.group(1).lower()


def write_timeline(stage: Path, pdf: Path, breaks: list[float], seconds: float) -> Path:
    import pymupdf
    from PIL import Image

    boundaries = [0.0, *breaks, seconds]
    png_dir = stage / "corrected_frames"
    png_dir.mkdir()
    files = []
    with pymupdf.open(pdf) as doc:
        if doc.page_count != len(boundaries)-1:
            raise VideoRepairError("Corrected PDF page count changed")
        for i, page in enumerate(doc):
            zoom = 1920.0 / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img.thumbnail((1920, 1080))
            canvas = Image.new("RGB", (1920, 1080), "white")
            canvas.paste(img, ((1920-img.width)//2, (1080-img.height)//2))
            file = png_dir / f"slide_{i+1:03d}.png"
            canvas.save(file)
            files.append(file)
    lines = ["ffconcat version 1.0"]
    for i, file in enumerate(files):
        seconds_on_slide = boundaries[i+1] - boundaries[i]
        if seconds_on_slide < 0.35:
            raise VideoRepairError("Invalid slide duration")
        # The filenames are owned by us and always contain only simple letters
        # and numbers. Use relative paths so the concat list is portable.
        lines.append(f"file 'corrected_frames/{file.name}'")
        lines.append(f"duration {seconds_on_slide:.6f}")
    lines.append(f"file 'corrected_frames/{files[-1].name}'")
    manifest = stage / "timeline.ffconcat"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def ensure_safe_paths(source_folder: Path, corrected_pdf: Path, output: Path) -> None:
    source_folder = source_folder.resolve()
    corrected_pdf = corrected_pdf.resolve()
    output = output.resolve()
    if output.exists():
        raise VideoRepairError("Output already exists; never overwrite")
    for protected in (source_folder, corrected_pdf.parent):
        if output == protected or protected in output.parents or output in protected.parents:
            raise VideoRepairError("Output must be independent of both inputs")
    if {part.casefold() for part in output.parts} & {
        "my drive", "google drive", "onedrive", "dropbox"
    }:
        raise VideoRepairError("Video candidates must reside on local disk")
    for p in (source_folder / "slides.pdf", source_folder / "slides.mp4", corrected_pdf):
        quality.require_file(p)


def inspect_source_timing_provenance(source_folder: Path, page_count: int) -> dict:
    """Detect stale sidecars/WAVs; never infer timing from their durations."""
    folder = Path(source_folder)
    result = {"expected_pages": page_count}
    sidecar = folder / "script_tts.json"
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
            slides = data["slides"]
            nums = [s["slide"] for s in slides]
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            raise VideoRepairError("Narration sidecar unreadable") from exc
        if nums != list(range(1, page_count + 1)):
            raise VideoRepairError(
                "Narration sidecar slide indices differ from current PDF"
            )
        result["narration_sidecar_sha256"] = quality.sha256(sidecar)
    numbered = {}
    for p in folder.iterdir():
        m = re.fullmatch(r"slide(\d+)\.wav", p.name, re.I)
        if m:
            number = int(m.group(1))
            if number in numbered:
                raise VideoRepairError("Duplicate numbered WAV slide")
            numbered[number] = p
    if numbered and set(numbered) != set(range(1, page_count + 1)):
        raise VideoRepairError(
            f"Stale WAV set: PDF has {page_count} slides, "
            f"but numbered WAVs are {sorted(numbered)}"
        )
    result["wav_files_present"] = len(numbered)
    result["wav_timing_used"] = False
    return result


def verify_candidate_synchronization(candidate: Path, corrected_pdf: Path,
                                     original_breaks: list[float], seconds: float,
                                     stage: Path, *, image_threshold: float = 11.0) -> dict:
    """Independently inspect the regenerated MP4, not just the source image files."""
    new_duration = media_duration(candidate)
    if abs(new_duration - seconds) > 0.35:
        raise VideoRepairError("Candidate MP4 duration differs from original")
    new_breaks = detect_scene_times(candidate, len(original_breaks) + 1, new_duration)
    timing_errors = [round(a-b, 3) for a, b in zip(new_breaks, original_breaks)]
    if max((abs(x) for x in timing_errors), default=0.0) > 0.4:
        raise VideoRepairError(f"Regenerated slide transitions shifted: {timing_errors}")
    verify_dir = stage / "candidate_visual_check"
    verify_dir.mkdir()
    samples = validate_visual_mapping(
        candidate, corrected_pdf, new_breaks, new_duration, verify_dir,
        max_distance=image_threshold
    )
    return {
        "corrected_video_seconds": new_duration,
        "candidate_boundaries_seconds": new_breaks,
        "scene_timing_error_seconds": timing_errors,
        "corrected_scene_validation": samples,
    }


def video_repair(source_folder: Path, corrected_pdf: Path, output: Path,
                 *, image_threshold: float = 11.0) -> dict:
    source_folder = Path(source_folder).resolve()
    corrected_pdf = Path(corrected_pdf).resolve()
    output = Path(output).resolve()
    ensure_safe_paths(source_folder, corrected_pdf, output)
    old_pdf = source_folder / "slides.pdf"
    old_mp4 = source_folder / "slides.mp4"
    # Confirm the PDF candidate is complete. We do NOT trust the WAV folder,
    # sidecar time estimates, or a guessed constant gap between slides.
    quality.check_slide_pdf(corrected_pdf, require_footer=True)
    comparison = compare_pages(old_pdf, corrected_pdf)
    provenance = inspect_source_timing_provenance(
        source_folder, comparison["pages"]
    )
    originals = {
        "old_pdf": quality.sha256(old_pdf),
        "old_mp4": quality.sha256(old_mp4),
        "corrected_pdf": quality.sha256(corrected_pdf)
    }
    seconds = media_duration(old_mp4)
    breaks = detect_scene_times(old_mp4, comparison["pages"], seconds)
    original_audio_hash = audio_stream_hash(old_mp4)

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".video-repair-", dir=output.parent))
    report = {
        "source_folder": str(source_folder), "corrected_pdf": str(corrected_pdf),
        "old_media_sha256": originals, "original_video_seconds": seconds,
        "video_slide_boundaries_seconds": breaks,
        "original_audio_sha256": original_audio_hash,
        "slide_comparison": comparison,
        "source_provenance": provenance,
        "publication_allowed": False,
        "completion_receipt_created": False,
        "academic_approval_asserted": False,
        "status": "STARTED"
    }
    try:
        report["visual_scene_validation"] = validate_visual_mapping(
            old_mp4, old_pdf, breaks, seconds, stage, max_distance=image_threshold
        )
        timeline = write_timeline(stage, corrected_pdf, breaks, seconds)
        candidate = stage / "corrected_slides.mp4"
        run_ffmpeg([
            "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(timeline),
            "-i", str(old_mp4), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", "30",
            "-c:a", "copy", "-t", f"{seconds:.3f}",
            "-movflags", "+faststart", str(candidate)
        ], timeout=300)
        new_audio_hash = audio_stream_hash(candidate)
        if new_audio_hash != original_audio_hash:
            raise VideoRepairError("Remux altered original compressed audio packets")
        quality.check_video(candidate)
        report["candidate_video_verification"] = verify_candidate_synchronization(
            candidate, corrected_pdf, breaks, seconds, stage,
            image_threshold=image_threshold
        )
        if {
            "old_pdf": quality.sha256(old_pdf), "old_mp4": quality.sha256(old_mp4),
            "corrected_pdf": quality.sha256(corrected_pdf)
        } != originals:
            raise VideoRepairError("Source media changed during repair")
        report["corrected_mp4_sha256"] = quality.sha256(candidate)
        report["candidate_seconds"] = media_duration(candidate)
        report["candidate_audio_sha256"] = new_audio_hash
        report["status"] = "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED"
        (stage / "video_repair_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        stage.rename(output)
    except Exception as exc:
        report["status"] = "VIDEO_CANDIDATE_FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        (stage / "video_repair_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (stage / "FAILED_NO_PUBLICATION.txt").write_text(
            "Video repair failed validation; this directory is NOT a valid release.\n",
            encoding="utf-8"
        )
        raise
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--corrected-pdf", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = video_repair(args.source, args.corrected_pdf, args.output)
    print(json.dumps({
        "status": result["status"],
        "original_video_seconds": result["original_video_seconds"],
        "corrected_mp4_sha256": result["corrected_mp4_sha256"],
        "original_audio_sha256": result["original_audio_sha256"],
        "candidate_audio_sha256": result["candidate_audio_sha256"],
        "slide_count": len(result["visual_scene_validation"])
    }, indent=2))


if __name__ == "__main__":
    main()
