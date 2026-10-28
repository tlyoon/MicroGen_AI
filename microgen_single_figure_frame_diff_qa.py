"""Independently confirm figure overlays change actual MP4 frames at WAV anchors.

Contrasts new figure-augmented MP4s with the original word-only MP4s;
requires both sets' independently decoded audio PCM evidence.
Not a proof of textbook figures, all-element sync or speech phonetics.
"""
from __future__ import annotations

import argparse
import io
import math
import subprocess
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageChops, ImageStat

from microgen_fresh_source_cues import source_inventory
from microgen_source_safe_orchestrator import atomic_json, digest, read_json


class FigureFrameDiffError(ValueError):
    pass


def frame_difference_metrics(old: Image.Image, new: Image.Image, image_box):
    """Region and whole-frame absolute difference, format-independent."""
    if old.size != new.size or old.size != (640, 360):
        raise FigureFrameDiffError("Expected two matching 640x360 decoded frames")
    left, top, right, bottom = map(int, image_box)
    if not (0 <= left < right <= 640 and 0 <= top < bottom <= 360):
        raise FigureFrameDiffError("Invalid figure bounds")
    diff = ImageChops.difference(old.convert("RGB"), new.convert("RGB"))
    inside = sum(ImageStat.Stat(diff.crop((left, top, right, bottom))).mean) / 3
    entire = sum(ImageStat.Stat(diff).mean) / 3
    return float(inside), float(entire)


def figure_change_visible(inside_mae: float, frame_mae: float) -> bool:
    """Require a substantial localized change, not global encoder noise."""
    return (math.isfinite(inside_mae) and math.isfinite(frame_mae) and
            inside_mae >= 12 and inside_mae >= 6 * max(frame_mae, .01))


def _decoded_frame(ffmpeg: Path, video: Path, when: float):
    cmd = [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
           "-ss", f"{when:.6f}", "-i", str(video), "-frames:v", "1",
           "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    try:
        raw = subprocess.check_output(cmd, timeout=30)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise FigureFrameDiffError("Cannot decode pinned MP4 sample") from exc


def audit_real_figure_frames(stage, anchor_receipt, old_dir, new_dir,
                             old_av_qa, new_av_qa, ffmpeg, destination):
    base, source = source_inventory(stage)
    paths = [Path(x).resolve(strict=True) for x in (
        anchor_receipt, old_dir, new_dir, old_av_qa, new_av_qa, ffmpeg)]
    anchors_file, before_dir, after_dir, old_qa_file, new_qa_file, ff = paths
    dest = Path(destination).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest == base or
            dest.is_relative_to(base) or base.is_relative_to(dest) or
            any(dest.is_relative_to(x) for x in
                (before_dir, after_dir, old_qa_file.parent,
                 new_qa_file.parent, anchors_file.parent)) or
            not ff.is_file()):
        raise FigureFrameDiffError("Use isolated output and real local FFmpeg")
    anchor = read_json(anchors_file)
    augmented_file = anchors_file.parent / "figure_augmented_word_cues.json"
    augmented = read_json(augmented_file)
    if (digest(augmented_file) != anchor.get("augmented_cue_report_sha256") or
            anchor.get("source_pdf_sha256") != digest(base / "slides.pdf")):
        raise FigureFrameDiffError("Original figure-cue manifest changed")
    old = read_json(before_dir / "highlighted_part_receipt.json")
    new = read_json(after_dir / "highlighted_part_receipt.json")
    independent_old = read_json(old_qa_file)
    independent_new = read_json(new_qa_file)
    if (anchor.get("source") != source or
            anchor.get("publication_allowed") is not False or
            anchor.get("figure_semantics_verified") is not False or
            old.get("source") != source or new.get("source") != source or
            old.get("cue_report_sha256") != anchor.get("base_cue_report_sha256") or
            new.get("cue_report_sha256") != anchor.get("augmented_cue_report_sha256") or
            independent_old.get("source") != source or
            independent_new.get("source") != source or
            any(data.get("publication_allowed") is not False for data in
                (old, new, independent_old, independent_new)) or
            not independent_old.get("full_pcm_hash_matches") or
            not independent_new.get("full_pcm_hash_matches")):
        raise FigureFrameDiffError("Untrusted source/audio/academic evidence")
    if (len(old.get("parts", [])) != 2 or
            len(new.get("parts", [])) != 2 or
            len(independent_old.get("parts", [])) != 2 or
            len(independent_new.get("parts", [])) != 2):
        raise FigureFrameDiffError("Both original and augmented video parts required")
    for i in range(2):
        lhs, rhs = old["parts"][i], new["parts"][i]
        qa1, qa2 = independent_old["parts"][i], independent_new["parts"][i]
        if (lhs.get("part") != i + 1 or rhs.get("part") != i + 1 or
                lhs.get("slides") != rhs.get("slides") or
                lhs.get("input_wav_sha256") != rhs.get("input_wav_sha256") or
                lhs.get("raw_audio_pcm_sha256") != rhs.get("raw_audio_pcm_sha256") or
                lhs.get("raw_audio_pcm_sha256") != qa1.get("decoded_audio_pcm_sha256") or
                rhs.get("raw_audio_pcm_sha256") != qa2.get("decoded_audio_pcm_sha256") or
                qa1.get("mp4_sha256") != lhs.get("video_sha256") or
                qa2.get("mp4_sha256") != rhs.get("video_sha256")):
            raise FigureFrameDiffError("Independent MP4/WAV evidence mismatch")
        for part, location in ((lhs, before_dir), (rhs, after_dir)):
            if (digest(location / part["video_file"]) != part["video_sha256"] or
                    not 0 < part["seconds"] < 600):
                raise FigureFrameDiffError("Real video hash or ten-minute rule failed")
    inputs = {str(p): digest(p) for p in (
        anchors_file, augmented_file, old_qa_file, new_qa_file,
        before_dir / "highlighted_part_receipt.json",
        after_dir / "highlighted_part_receipt.json",
        base / "slides.pdf")}
    rows = []
    candidates = anchor.get("candidate_slides")
    if (not isinstance(candidates, list) or
            sum(len(row.get("cues", [])) for row in candidates) !=
            anchor.get("figure_anchor_cue_count") or
            anchor.get("figure_anchor_cue_count", 0) < 1):
        raise FigureFrameDiffError("No valid original figure-cue inventory")
    with fitz.open(base / "slides.pdf") as doc:
        for entry in candidates:
            slide = entry["slide"]
            if type(slide) is not int or not 1 <= slide <= source["slide_count"]:
                raise FigureFrameDiffError("Invalid original slide")
            part = 1 if slide <= 13 else 2
            first = 1 if part == 1 else 14
            offset = sum(source["wav_inventory"][n-1]["duration_seconds"]
                         for n in range(first, slide))
            page = doc[slide - 1]
            scale = min(640 / page.rect.width, 360 / page.rect.height)
            margin = ((640 - page.rect.width * scale) / 2,
                      (360 - page.rect.height * scale) / 2)
            lhs, rhs = old["parts"][part-1], new["parts"][part-1]
            for cue in entry["cues"]:
                if cue not in augmented["slides"][slide-1]["cues"]:
                    raise FigureFrameDiffError("Rendered figure anchor not in pinned cues")
                if cue.get("figure_semantics_verified") is not False:
                    raise FigureFrameDiffError("Forged figure semantics")
                box = cue["box"]
                pixel_box = (
                    max(0, math.floor(box[0] * scale + margin[0])),
                    max(0, math.floor(box[1] * scale + margin[1])),
                    min(640, math.ceil(box[2] * scale + margin[0])),
                    min(360, math.ceil(box[3] * scale + margin[1])))
                at = offset + (cue["start"] + cue["end"]) / 2
                before = _decoded_frame(ff, before_dir / lhs["video_file"], at)
                after = _decoded_frame(ff, after_dir / rhs["video_file"], at)
                local, entire = frame_difference_metrics(before, after, pixel_box)
                visible = figure_change_visible(local, entire)
                rows.append({"slide": slide, "part": part, "mp4_time": round(at, 4),
                    "inside_figure_mae": round(local, 3),
                    "whole_frame_mae": round(entire, 3),
                    "incremental_figure_overlay_visible": visible,
                    "mathematical_figure_semantics_verified": False})
    if (not rows or not all(row["incremental_figure_overlay_visible"] for row in rows)
            or source_inventory(base)[1] != source or
            any(digest(Path(name)) != sha for name, sha in inputs.items()) or
            any(digest(folder / part["video_file"]) != part["video_sha256"]
                for folder, batch in ((before_dir, old), (after_dir, new))
                for part in batch["parts"])):
        raise FigureFrameDiffError("Figure overlay not verified or sources changed")
    dest.mkdir(parents=True, exist_ok=False)
    report = {"schema_version":1,
        "status":"ACTUAL_DIFFERENTIAL_FIGURE_PIXEL_QA_NOT_SEMANTIC_APPROVAL",
        "source":source,"source_file_sha256":inputs,
        "anchor_count":len(rows),"incremental_overlay_check_count":len(rows),
        "all_figure_overlays_visibly_changed":True,
        "measured_samples":rows,"video_pcm_matches_original":True,
        "figure_semantics_verified":False,
        "full_element_synchronization_verified":False,
        "phonetic_correctness_verified":False,"publication_allowed":False}
    atomic_json(dest / "figure_frame_difference_receipt.json", report)
    return report


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    for arg in ("stage","anchor_receipt","old_dir","new_dir",
                "old_av_qa","new_av_qa","ffmpeg","destination"):
        p.add_argument("--"+arg.replace("_","-"),required=True)
    a=p.parse_args()
    r=audit_real_figure_frames(a.stage,a.anchor_receipt,a.old_dir,a.new_dir,
        a.old_av_qa,a.new_av_qa,a.ffmpeg,a.destination)
    print({"validated_overlay_frames":r["incremental_overlay_check_count"],
           "publication_allowed":False})
