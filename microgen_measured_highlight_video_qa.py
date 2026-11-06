"""Independent decoded-frame QA for source/PDF/PCM-bound element highlighting.

Reuses the proven PR209 independent PDF/MP4 ROI-difference primitives rather
than inventing another encoder or shortcut. This is *visual timing only*:
it cannot certify phonetic alignment, math semantics or publication rights.
"""
from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path

from PIL import Image

from microgen_timed_highlight_contract import (
    MANIFEST, inspect_timed_highlights,
)
from microgen_quality import check_video, sha256
from microgen_single_figure_frame_diff_qa import (
    _decoded_frame, frame_difference_metrics, figure_change_visible,
)

RECEIPT = ".microgen_visual_highlight_qa.json"
SIZE = (640, 360)
MIN_SAMPLE_CUE_SECONDS = 0.45
MAX_VISUAL_INSIDE_UNHIGHLIGHTED_MAE = 8.5


class MeasuredVisualQAError(RuntimeError):
    """Source, elapsed-timing or decoded-MP4 highlights unverified."""


def _pdf_reference(page) -> Image.Image:
    import fitz
    width, height = SIZE
    zoom = min(width / page.rect.width, height / page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False)
    if pix.n != 3:
        raise MeasuredVisualQAError("Unexpected PDF source pixel mode")
    raw = Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
    if raw.width>width or raw.height>height:
        raw.thumbnail((width,height),resample=Image.Resampling.LANCZOS)
    reference=Image.new("RGB",SIZE,"white")
    reference.paste(raw,((width-raw.width)//2,(height-raw.height)//2))
    return reference


def _pixel_box(page, cue: dict) -> tuple[int,int,int,int]:
    pw,ph=float(page.rect.width),float(page.rect.height)
    zoom=min(SIZE[0]/pw,SIZE[1]/ph)
    dx=(SIZE[0]-pw*zoom)/2
    dy=(SIZE[1]-ph*zoom)/2
    x0,y0,x1,y1=map(float,cue["pdf_bbox"])
    box=(int(round(dx+x0*zoom)),int(round(dy+y0*zoom)),
         int(round(dx+x1*zoom)),int(round(dy+y1*zoom)))
    if (box[0]<0 or box[1]<0 or box[2]>SIZE[0] or box[3]>SIZE[1]
            or box[2]-box[0]<3 or box[3]-box[1]<3):
        raise MeasuredVisualQAError("PDF cue too small or outside displayed frame")
    return box


def _frame(ffmpeg: Path, video: Path, when: float) -> Image.Image:
    image=_decoded_frame(ffmpeg,video,when)
    return image.resize(SIZE,resample=Image.Resampling.BILINEAR)


def _inputs(stage: Path, count: int, *,
            video_override: Path | None = None,
            verified_parts: list[dict] | None = None) -> dict[str,str]:
    source=["slides.pdf","script_tts.json","slides.mp4",MANIFEST]
    source += [f"slide{i}.pdf" for i in range(1,count+1)]
    source += [f"slide{i}.wav" for i in range(1,count+1)]
    manifest=json.loads((stage/MANIFEST).read_text(encoding="utf8"))
    source += [cue["audio_chunk"] for entry in manifest["slides"]
               for cue in entry["cues"]]
    if verified_parts is not None:
        # Hash the source-bound part inventory and *every* delivered MP4.
        # The old single-MP4 receipt shape remains byte-for-byte unchanged.
        source.append(".microgen_autonomous_parts.json")
        source += [part["file"] for part in verified_parts]
    if len(source)!=len(set(source)):
        raise MeasuredVisualQAError("Ambiguous or duplicated media input")
    return {name:sha256(video_override if (name=="slides.mp4" and
                                              video_override is not None)
                        else stage/name) for name in source}


def inspect_visual_timing(stage: Path, *, ffmpeg: Path,
                          video_override: Path | None = None) -> dict:
    """Re-decode the actual MP4; optionally verify a candidate before commit."""
    import fitz
    stage=Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise MeasuredVisualQAError("Untrusted private video stage")
    ffmpeg=Path(ffmpeg)
    if not ffmpeg.is_file():
        raise MeasuredVisualQAError("Verified local FFmpeg executable required")
    timed=inspect_timed_highlights(stage)
    if (timed["visual_highlight_rendering_verified"] is not False or
        timed["publication_allowed"] is not False):
        raise MeasuredVisualQAError("Source cue evidence overstated release")
    count=timed["slide_count"]
    slides=timed["slides"]
    expected=sum(row["duration_seconds"] for row in slides)
    video_path=Path(video_override) if video_override is not None else stage/"slides.mp4"
    if video_path.is_symlink() or not video_path.is_file():
        raise MeasuredVisualQAError("Missing or unsafe decoded video candidate")
    video=check_video(video_path,expected_seconds=expected)
    if not math.isfinite(video["seconds"]) or video["seconds"]<=0:
        raise MeasuredVisualQAError("Invalid decoded full-video duration")

    # Source-bound whole-slide parts are already checked for ordering, hashes,
    # complete slide coverage, durations and immutable cache provenance by
    # the established autonomous multipart verifier. Reuse that contract.
    part_inventory=None
    slide_media={}
    if video["seconds"] >= 600:
        if video_override is not None:
            raise MeasuredVisualQAError(
                "Long candidate needs independently verified staged video parts")
        from microgen_autonomous_video_parts import verify_receipt as verify_parts
        parts=verify_parts(stage)["parts"]
        if not 2<=len(parts)<=100:
            raise MeasuredVisualQAError("Long lecture needs multiple verified parts")
        part_inventory=[]
        for part in parts:
            ids=part["slides"]
            name=part["file"]
            path=stage/name
            if path.is_symlink() or not path.is_file():
                raise MeasuredVisualQAError("Missing or unsafe ordered video part")
            total=sum(slides[i-1]["duration_seconds"] for i in ids)
            if total<=0 or total>=600:
                raise MeasuredVisualQAError("Unsafe source-derived part duration")
            media=check_video(path,expected_seconds=total)
            if media["seconds"]>=600:
                raise MeasuredVisualQAError("Delivered part exceeds 600-second limit")
            offset=0.0
            for slide_id in ids:
                if slide_id in slide_media:
                    raise MeasuredVisualQAError("Duplicate slide in highlighted parts")
                slide_media[slide_id]=(path,offset,total)
                offset+=slides[slide_id-1]["duration_seconds"]
            part_inventory.append({"file":name,"slides":list(ids)})
        if sorted(slide_media)!=list(range(1,count+1)):
            raise MeasuredVisualQAError("Highlight parts omit source slides")
    else:
        offset=0.0
        for slide_id,row in enumerate(slides,1):
            slide_media[slide_id]=(video_path,offset,expected)
            offset+=row["duration_seconds"]
    checks=[]
    elapsed=0.0
    with fitz.open(str(stage/"slides.pdf")) as doc:
        if doc.page_count!=count:
            raise MeasuredVisualQAError("Video has wrong source slide count")
        for slide,row in enumerate(slides,1):
            page=doc[slide-1]
            reference=_pdf_reference(page)
            elements=row["elements"]
            if not elements:
                raise MeasuredVisualQAError("No highlighted source elements")
            cue_centers=[]
            for cue in elements:
                duration=cue["end_seconds"]-cue["start_seconds"]
                if duration < MIN_SAMPLE_CUE_SECONDS:
                    raise MeasuredVisualQAError(
                        "Cue too short for robust independent 10fps validation")
                center=(cue["start_seconds"]+cue["end_seconds"])/2
                cue_centers.append(center)
            snapshots={}
            current_video,video_offset,video_limit=slide_media[slide]
            for i,center in enumerate(cue_centers):
                at=video_offset+center
                if at<0 or at>=video_limit:
                    raise MeasuredVisualQAError("Invalid part-local cue timestamp")
                snapshots[i]=_frame(ffmpeg,current_video,at)
            for i,cue in enumerate(elements):
                roi=_pixel_box(page,cue)
                active_inside,frame_mae=frame_difference_metrics(
                    reference,snapshots[i],roi)
                if not figure_change_visible(active_inside,frame_mae):
                    raise MeasuredVisualQAError(
                        f"Slide {slide} element {i+1}: no independently "
                        "visible localized highlight in decoded MP4")
                inactive_inside=None
                if len(elements)>1:
                    candidate=(i+1)%len(elements)
                    inactive_inside,_=frame_difference_metrics(
                        reference,snapshots[candidate],roi)
                    if inactive_inside>MAX_VISUAL_INSIDE_UNHIGHLIGHTED_MAE:
                        raise MeasuredVisualQAError(
                            f"Slide {slide} element {i+1}: highlight "
                            "remained present outside its PCM cue")
                check={
                    "slide":slide,"element_id":cue["element_id"],
                    "global_center_seconds":round(elapsed+cue_centers[i],6),
                    "active_roi_mae":round(active_inside,3),
                    "whole_frame_mae":round(frame_mae,3),
                    "inactive_roi_mae":(
                        round(inactive_inside,3) if inactive_inside is not None else None),
                    "active_localized":True,
                    "off_control_checked":inactive_inside is not None,
                }
                if part_inventory is not None:
                    check["deliverable_video"]=current_video.name
                    check["part_center_seconds"]=round(
                        video_offset+cue_centers[i],6)
                checks.append(check)
            elapsed+=row["duration_seconds"]
    if len(checks)!=sum(len(x["elements"]) for x in slides):
        raise MeasuredVisualQAError("Not all source-grounded cues checked")
    report={
        "status":"SOURCE_PCM_TIMED_VISUAL_HIGHLIGHTS_INDEPENDENTLY_CHECKED",
        "slide_count":count,"cue_count":len(checks),
        "checked_cues":checks,
        "source_and_video_sha256":_inputs(
            stage,count,video_override=video_path,
            verified_parts=part_inventory),
        "visual_highlight_rendering_verified":True,
        "spoken_word_to_element_alignment_verified":False,
        "academic_correctness_verified":False,
        "publication_allowed":False,
    }
    if part_inventory is not None:
        report["verified_delivery_parts"]=part_inventory
    return report


def audit_stage(stage: Path, *, ffmpeg: Path) -> dict:
    """Create a private, immutable receipt only after all decoded checks pass."""
    stage=Path(stage)
    target=stage/RECEIPT
    if target.exists() or target.is_symlink():
        return verify_receipt(stage,ffmpeg=ffmpeg)
    data=inspect_visual_timing(stage,ffmpeg=ffmpeg)
    if _inputs(stage,data["slide_count"],
               verified_parts=data.get("verified_delivery_parts"))!=(
                   data["source_and_video_sha256"]):
        raise MeasuredVisualQAError("Source or encoded output changed during QA")
    with target.open("x",encoding="utf8") as out:
        json.dump(data,out,ensure_ascii=False,indent=2)
    try:
        verify_receipt(stage,ffmpeg=ffmpeg)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return data


def verify_receipt(stage: Path, *, ffmpeg: Path) -> dict:
    stage=Path(stage)
    target=stage/RECEIPT
    if target.is_symlink() or not target.is_file():
        raise MeasuredVisualQAError("Missing independent decoded-video QA receipt")
    stored=json.loads(target.read_text(encoding="utf8"))
    if (stored.get("publication_allowed") is not False or
        stored.get("spoken_word_to_element_alignment_verified") is not False):
        raise MeasuredVisualQAError("Untrusted visual QA rights or phoneme claim")
    current=inspect_visual_timing(stage,ffmpeg=ffmpeg)
    if stored!=current:
        raise MeasuredVisualQAError("Decoded video or source cue evidence drifted")
    return stored


def main() -> None:
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage",type=Path,default=Path.cwd())
    p.add_argument("--ffmpeg",type=Path,required=True)
    opt=p.parse_args()
    report=audit_stage(opt.stage,ffmpeg=opt.ffmpeg)
    print(json.dumps({
        "status":report["status"],"slide_count":report["slide_count"],
        "cue_count":report["cue_count"],
        "publication_allowed":False,
    }))


if __name__=="__main__":
    main()
