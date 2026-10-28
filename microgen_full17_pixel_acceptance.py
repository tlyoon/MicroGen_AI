"""Check every full-lecture source-PDF word overlay in the actual remuxed MP4.

Purely technical before/during pixel timing, NOT reliable phoneme
transcription or complete narrated mathematical formula/figure alignment.
"""
from __future__ import annotations
import json
import math
import subprocess
import tempfile
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
import pymupdf as fitz
from microgen_source_safe_orchestrator import (
    OrchestratorError,verify_workspace,read_json,atomic_json,digest
)

class WholeVideoPixelError(OrchestratorError):
    pass

def _still(ff,video,seconds,output):
    cmd=[str(ff),"-nostdin","-hide_banner","-loglevel","error",
         "-ss",f"{seconds:.5f}","-i",str(video),"-frames:v","1",
         "-y",str(output)]
    try:
        result=subprocess.run(cmd,capture_output=True,timeout=45)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise WholeVideoPixelError("Video frame extraction failed") from e
    if result.returncode or not output.is_file():
        raise WholeVideoPixelError("Frame missing at expected video clock")

def check_all_full17_highlights(workspace,output,*,ffmpeg,threshold=2.5):
    root=Path(workspace).resolve(strict=True)
    doc=verify_workspace(root)
    target=Path(output).resolve(strict=False)
    if target.exists() or target.is_symlink() or target==root or target.is_relative_to(root/"audio"):
        raise WholeVideoPixelError("Refuse to overwrite existing pixel QA evidence")
    if (type(threshold) not in (int,float) or not math.isfinite(threshold)
        or not 1<=threshold<=100):
        raise WholeVideoPixelError("Unbounded pixel contrast threshold")
    source=Path(doc["source_root"]).resolve(strict=True)
    if (target==source or target.is_relative_to(source) or
        target==root or target.is_relative_to(root)):
        raise WholeVideoPixelError("QA report must be outside protected teaching and media stages")
    final=root/"complete_decoded_pcm_candidate"/"full_pcm_candidate_receipt.json"
    receipt=read_json(final)
    if (receipt.get("status")!="COMPLETE_17_SLIDE_PCM_EXACT_TECHNICAL_CANDIDATE"
       or receipt.get("publication_allowed") is not False
       or receipt.get("all_original_decoded_PCM_samples_preserved") is not True):
        raise WholeVideoPixelError("Actual validated complete source PCM candidate required")
    video=Path(receipt["video_path"]).resolve(strict=True)
    if video.is_symlink() or digest(video)!=receipt["video_sha256"]:
        raise WholeVideoPixelError("Published candidate MP4 has changed")
    if digest(source/"slides.pdf")!=doc["source_pdf_sha256"]:
        raise WholeVideoPixelError("Original source PDF has changed")
    renders=read_json(root/"render_receipt.json")["slides"]
    cues=read_json(root/"cues.json")["elements"]
    if ([x["slide"] for x in renders]!=list(range(1,18))
        or not 1<=len(cues)<=128):
        raise WholeVideoPixelError("Incomplete slide render or unbounded highlights")
    ff=Path(ffmpeg)
    if not ff.is_file():raise WholeVideoPixelError("Explicit FFmpeg executable required")
    results=[]
    with fitz.open(source/"slides.pdf") as pdf, tempfile.TemporaryDirectory(prefix="microgen_combined_pixels_") as temp:
        if pdf.page_count!=17:raise WholeVideoPixelError("Original 17-page PDF required")
        t=Path(temp)
        visual_starts={}
        elapsed=0.
        for row in renders:
            if not 0<row["duration_seconds"]<600:
                raise WholeVideoPixelError("Invalid individual rendered video duration")
            visual_starts[row["slide"]]=elapsed
            elapsed+=row["duration_seconds"]
        for index,cue in enumerate(cues,1):
            slide=cue.get("slide")
            if type(slide) is not int or slide not in visual_starts:
                raise WholeVideoPixelError("Invalid slide cue identity")
            page=pdf[slide-1]
            x0,y0,x1,y1=cue["box"]
            lstart,lend=cue["local_start"],cue["local_end"]
            if (not all(type(v) in (float,int) and math.isfinite(v)
                    for v in (x0,y0,x1,y1,lstart,lend))
                or not 0<=x0<x1<=page.rect.width or
                not 0<=y0<y1<=page.rect.height or
                not 0<=lstart<lend<=renders[slide-1]["duration_seconds"]+.05):
                raise WholeVideoPixelError("Invalid source geometry or cue timing")
            start=visual_starts[slide]+lstart
            end=visual_starts[slide]+lend
            before=max(.01,start-.55)
            during=(start+end)/2
            if during>=receipt["video_seconds"]:
                raise WholeVideoPixelError("Cue after actual candidate playback endpoint")
            a=t/f"off{index:03}.png";b=t/f"on{index:03}.png"
            _still(ff,video,before,a)
            _still(ff,video,during,b)
            pw,ph=page.rect.width,page.rect.height
            scale=min(1280/pw,720/ph)
            ox=(1280-pw*scale)/2;oy=(720-ph*scale)/2
            region=(max(0,round(ox+x0*scale)-10),
                    max(0,round(oy+y0*scale)-10),
                    min(1280,round(ox+x1*scale)+10),
                    min(720,round(oy+y1*scale)+10))
            if region[0]>=region[2] or region[1]>=region[3]:
                raise WholeVideoPixelError("PDF cue box outside output frame")
            with Image.open(a) as prior,Image.open(b) as at:
                if prior.size!=(1280,720) or at.size!=(1280,720):
                    raise WholeVideoPixelError("Unexpected encoded frame resolution")
                delta=ImageChops.difference(prior.convert("RGB").crop(region),
                         at.convert("RGB").crop(region))
                mean=sum(ImageStat.Stat(delta).mean)/3
            results.append({"slide":slide,"cue":index,"word":cue["text"],
                "sample_before_seconds":round(before,5),
                "sample_during_seconds":round(during,5),
                "mean_rgb_difference":round(mean,4),
                "highlight_pixel_change_verified":mean>threshold})
            a.unlink(missing_ok=True);b.unlink(missing_ok=True)
    if digest(video)!=receipt["video_sha256"] or digest(source/"slides.pdf")!=doc["source_pdf_sha256"]:
        raise WholeVideoPixelError("Original source/final candidate was modified")
    passed=sum(r["highlight_pixel_change_verified"] for r in results)
    report={"schema_version":1,
       "status":"ALL_VISUAL_CUES_VERIFIED" if passed==len(results) else "PARTIAL_VISUAL_CUES_REQUIRE_REPAIR",
       "source_mp4_sha256":receipt["source_mp4_sha256"],
       "candidate_video_sha256":receipt["video_sha256"],
       "cue_count":len(results),"visual_cues_verified":passed,
       "checks":results,
       "all_visual_cues_verified":passed==len(results),
       "actual_spoken_word_identity_verified":False,
       "math_equation_figure_semantics_verified":False,
       "pronunciation_approved":False,"publication_allowed":False}
    atomic_json(target,report)
    return {"report":str(target),"checked":len(results),"passed":passed,
            "failed":len(results)-passed,"all_visual_cues_verified":passed==len(results),
            "publication_allowed":False}
