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
# The decoded H.264 frame and an independently rasterized PDF are not
# pixel-identical even when no overlay is present. A source ROI with static
# render bias >8.5 must still show decisive on/off *decoded-frame* contrast,
# and its off-state signal must be a small fraction of its active signal.
MIN_CALIBRATED_ON_OFF_GAP_MAE = 20.0
MIN_DECODED_TEMPORAL_CHANGE_MAE = 25.0
MAX_OFF_TO_ACTIVE_SIGNAL_RATIO = 0.30
# Regions shared by separate source-grounded cues are not independent
# off-controls. Exclude those frames, but require a genuine non-overlapping
# control for every PDF region on a multi-cue slide.
MAX_OFF_CONTROL_SOURCE_ROI_OVERLAP_FRACTION = 0.02
# When an entire highlighted text block covers a substantial fraction of
# the frame, that overlay also increases whole-frame MAE. The previous
# fixed 6x ROI/frame threshold can then be mathematically unattainable.
MIN_TIMED_LARGE_ROI_ACTIVE_MAE = 20.0
MIN_LARGE_ROI_FRACTION_OF_POSSIBLE_CONTRAST = 0.75
# The generic media probe allows up to 4% runtime drift. That is too loose
# for a timed highlight cue audit, so independently bound each part clock.
MAX_PART_AUDIO_CLOCK_DRIFT_SECONDS = 1.0


class MeasuredVisualQAError(RuntimeError):
    """Source, elapsed-timing or decoded-MP4 highlights unverified."""


def _off_control_verified(*, active:float, inactive:float,
                          temporal_change:float) -> bool:
    """Distinguish static PDF/H.264 rasterization bias from a stuck overlay.

    Never approve merely because the inactive PDF-frame score is nonzero:
    require actual decoded-frame temporal contrast and small off/on ratio.
    """
    if not all(math.isfinite(x) and x >= 0 for x in
               (active,inactive,temporal_change)):
        return False
    if inactive <= MAX_VISUAL_INSIDE_UNHIGHLIGHTED_MAE:
        return True
    return (active-inactive >= MIN_CALIBRATED_ON_OFF_GAP_MAE
            and temporal_change >= MIN_DECODED_TEMPORAL_CHANGE_MAE
            and inactive <= active*MAX_OFF_TO_ACTIVE_SIGNAL_RATIO)


def _timed_source_region_visible(active:float,frame_mae:float,
                                 roi:tuple[int,int,int,int], *,
                                 independently_controlled:bool) -> bool:
    """PDF-vs-decoded localized contrast with an ROI-area-aware ceiling.

    The fallback is permitted only when independent decoded-frame off
    controls also exist. It cannot approve a static full-frame change or
    a large ROI with no distinct source control.
    """
    if figure_change_visible(active,frame_mae):
        return True
    if (not independently_controlled or
            not math.isfinite(active) or not math.isfinite(frame_mae)
            or active<MIN_TIMED_LARGE_ROI_ACTIVE_MAE or frame_mae<0):
        return False
    area=(roi[2]-roi[0])*(roi[3]-roi[1])
    if area<=0 or area>SIZE[0]*SIZE[1]:
        return False
    required_ratio=min(
        6.0,MIN_LARGE_ROI_FRACTION_OF_POSSIBLE_CONTRAST*
        SIZE[0]*SIZE[1]/area)
    return active>=required_ratio*max(frame_mae,0.01)


def _source_roi_overlap_fraction(roi:tuple[int,int,int,int],
                                 other:tuple[int,int,int,int]) -> float:
    """How much of this PDF source region is active in another cue?"""
    width=max(0,min(roi[2],other[2])-max(roi[0],other[0]))
    height=max(0,min(roi[3],other[3])-max(roi[1],other[1]))
    area=(roi[2]-roi[0])*(roi[3]-roi[1])
    if area<=0:
        raise MeasuredVisualQAError("Invalid source ROI for off-control")
    return width*height/area


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
            if abs(media["seconds"]-total)>MAX_PART_AUDIO_CLOCK_DRIFT_SECONDS:
                raise MeasuredVisualQAError(
                    "Delivered part media clock drifts from source PCM timing")
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
            # Geometrically shared regions are legitimately highlighted
            # during each cue that references them; they cannot serve as
            # independent controls for one another.
            source_rois=[]
            for cue in elements:
                regions=cue.get("pdf_bboxes",[cue["pdf_bbox"]])
                if not isinstance(regions,list) or not regions:
                    raise MeasuredVisualQAError("Missing grouped highlight regions")
                source_rois.append([
                    _pixel_box(page,{"pdf_bbox":region}) for region in regions])
            for i,cue in enumerate(elements):
                rois=source_rois[i]
                active_scores=[]
                frame_scores=[]
                inactive_scores=[]
                decoded_transition_scores=[]
                overlapping_off_control_skips=0
                for roi in rois:
                    active,frame_mae=frame_difference_metrics(
                        reference,snapshots[i],roi)
                    if not _timed_source_region_visible(
                            active,frame_mae,roi,
                            independently_controlled=len(elements)>1):
                        raise MeasuredVisualQAError(
                            f"Slide {slide} element {i+1}: one PDF source region "
                            "has no independently visible decoded highlight")
                    active_scores.append(active)
                    frame_scores.append(frame_mae)
                    if len(elements)>1:
                        # Check every truly OFF cue, not only the next. A
                        # different narration cue which highlights the same
                        # source region is an ON state, not an off-control.
                        # The actual decoded temporal transition rejects
                        # persistent overlays while tolerating static PDF
                        # rasterization bias.
                        off_control_count=0
                        for candidate in range(len(elements)):
                            if candidate==i:
                                continue
                            if any(_source_roi_overlap_fraction(roi,other)
                                   > MAX_OFF_CONTROL_SOURCE_ROI_OVERLAP_FRACTION
                                   for other in source_rois[candidate]):
                                overlapping_off_control_skips+=1
                                continue
                            off_control_count+=1
                            inactive,_=frame_difference_metrics(
                                reference,snapshots[candidate],roi)
                            temporal,_=frame_difference_metrics(
                                snapshots[i],snapshots[candidate],roi)
                            if not _off_control_verified(
                                    active=active,inactive=inactive,
                                    temporal_change=temporal):
                                raise MeasuredVisualQAError(
                                    f"Slide {slide} element {i+1}: one grouped "
                                    "source region remained highlighted outside its PCM cue")
                            inactive_scores.append(inactive)
                            decoded_transition_scores.append(temporal)
                        if not off_control_count:
                            raise MeasuredVisualQAError(
                                f"Slide {slide} element {i+1}: no independent "
                                "nonoverlapping source-region off-control")
                active_inside=min(active_scores)
                frame_mae=max(frame_scores)
                inactive_inside=max(inactive_scores) if inactive_scores else None
                check={
                    "slide":slide,"element_id":cue["element_id"],
                    "global_center_seconds":round(elapsed+cue_centers[i],6),
                    "active_roi_mae":round(active_inside,3),
                    "whole_frame_mae":round(frame_mae,3),
                    "inactive_roi_mae":(
                        round(inactive_inside,3) if inactive_inside is not None else None),
                    "decoded_on_off_min_mae":(
                        round(min(decoded_transition_scores),3)
                        if decoded_transition_scores else None),
                    "calibrated_render_baseline":any(
                        score>MAX_VISUAL_INSIDE_UNHIGHLIGHTED_MAE
                        for score in inactive_scores),
                    "off_control_sample_count":len(inactive_scores),
                    "overlapping_source_control_exclusions":
                        overlapping_off_control_skips,
                    "active_localized":True,
                    "off_control_checked":inactive_inside is not None,
                }
                if len(rois)>1:
                    check["verified_group_regions"]=len(rois)
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
