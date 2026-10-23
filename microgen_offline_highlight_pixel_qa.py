"""Video pixel evidence for individually timed source-PDF highlight cues.

Confirms highlighted pixels appear at an existing ASR-proposed timestamp.
This cannot certify that the recognizer transcribed the correct spoken word
or that the highlighted text is the mathematical expression being discussed.
"""
from __future__ import annotations
import json
import math
import subprocess
import tempfile
from pathlib import Path

import pymupdf as fitz
from PIL import Image,ImageChops,ImageStat
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,OrchestratorError

class PixelEvidenceError(OrchestratorError):
    pass

def _frame(video,time,ffmpeg,output):
    cmd=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error",
         "-i",str(video),"-ss",f"{time:.5f}",
         "-frames:v","1","-y",str(output)]
    try:
        r=subprocess.run(cmd,capture_output=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise PixelEvidenceError("Video frame sampling unavailable") from e
    if r.returncode or not output.is_file():
        raise PixelEvidenceError("Could not decode requested video frame")

def verify_highlight_pixels(candidate_folder,original_pdf,ffmpeg,output,
                            *,minimum_rgb_mean_difference=2.5):
    root=Path(candidate_folder).resolve(strict=True)
    pdf=Path(original_pdf).resolve(strict=True)
    destination=Path(output).resolve(strict=False)
    if destination.exists() or destination.is_symlink():
        raise PixelEvidenceError("Cannot overwrite video pixel report")
    receipt=read_json(root/"candidate_receipt.json")
    if receipt.get("publication_allowed") is not False:
        raise PixelEvidenceError("Nonpublishing candidate receipt required")
    if digest(pdf)!=receipt.get("source_pdf_sha256"):
        raise PixelEvidenceError("Original PDF checksum drift")
    slide=receipt.get("slide")
    if type(slide) is not int or slide<1:
        raise PixelEvidenceError("Invalid source-PDF slide")
    cues=receipt.get("cues")
    if not isinstance(cues,list) or not 1<=len(cues)<=64:
        raise PixelEvidenceError("Bounded source-PDF cues required")
    media=list((root/"media").glob("*.mp4"))
    if len(media)!=1 or media[0].is_symlink() or digest(media[0])!=receipt.get("video_sha256"):
        raise PixelEvidenceError("Rendered candidate MP4 changed")
    ff=Path(ffmpeg)
    if not ff.is_file():raise PixelEvidenceError("FFmpeg missing")
    if not type(minimum_rgb_mean_difference) in (float,int) or not 1<=minimum_rgb_mean_difference<=100:
        raise PixelEvidenceError("Invalid pixel-change floor")
    with fitz.open(pdf) as doc:
        if slide>doc.page_count:raise PixelEvidenceError("Missing PDF page")
        page=doc[slide-1]
        w,h=page.rect.width,page.rect.height
    scale=min(1280/w,720/h)
    ox=(1280-w*scale)/2
    oy=(720-h*scale)/2
    checks=[]
    with tempfile.TemporaryDirectory(prefix="microgen_offline_pixel_") as tmp:
        t=Path(tmp)
        for i,cue in enumerate(cues,1):
            start,end=cue["start_seconds"],cue["end_seconds"]
            if (not all(type(v) in (float,int) and math.isfinite(v)
                        for v in (start,end,*cue["box"]))
                or not .05<start<end<receipt["video_seconds"]
                or end-start<.09):
                raise PixelEvidenceError("Invalid cue timing or source box")
            before=max(.01,start-.55)
            during=(start+end)/2
            a,b=t/f"before_{i}.png",t/f"during_{i}.png"
            _frame(media[0],before,ff,a)
            _frame(media[0],during,ff,b)
            x0,y0,x1,y1=cue["box"]
            region=(max(0,round(ox+x0*scale)-10),
                    max(0,round(oy+y0*scale)-10),
                    min(1280,round(ox+x1*scale)+10),
                    min(720,round(oy+y1*scale)+10))
            if region[0]>=region[2] or region[1]>=region[3]:
                raise PixelEvidenceError("PDF cue box outside real video frame")
            with Image.open(a) as old,Image.open(b) as new:
                if old.size!=(1280,720) or new.size!=(1280,720):
                    raise PixelEvidenceError("Unexpected video frame geometry")
                delta=ImageChops.difference(old.convert("RGB").crop(region),
                          new.convert("RGB").crop(region))
                mean=sum(ImageStat.Stat(delta).mean)/3
            checks.append({"cue":i,"text":cue["text"],
                "before_seconds":round(before,5),"during_seconds":round(during,5),
                "mean_rgb_difference":round(mean,4),
                "timed_visual_change_detected":mean>minimum_rgb_mean_difference})
    if not all(c["timed_visual_change_detected"] for c in checks):
        raise PixelEvidenceError("Missing expected on-screen highlight in real MP4")
    if digest(pdf)!=receipt["source_pdf_sha256"] or digest(media[0])!=receipt["video_sha256"]:
        raise PixelEvidenceError("Source PDF/video changed during QA")
    result={"status":"SOURCE_BOUND_ASR_CUE_VISUAL_PIXEL_CHECK_PASSED",
       "slide":slide,"candidate_mp4_sha256":receipt["video_sha256"],
       "pdf_sha256":receipt["source_pdf_sha256"],
       "checks":checks,"all_cue_pixels_detected":True,
       "recognised_word_sound_certified":False,
       "math_figure_semantics_certified":False,
       "complete_lesson_sync_certified":False,
       "publication_allowed":False,"source_modified":False}
    atomic_json(destination,result)
    return {"status":result["status"],"verified_cues":len(checks),
            "publication_allowed":False,"report":str(destination)}
