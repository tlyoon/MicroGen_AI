"""Independent rendered slide pixel QA for corrected §2.5 (not academic QA).

Render a new reference from the SHA-pinned PDF, then seek into the actual
MP4 before/after boundaries. Never trust the candidate's own cached PNGs.
Each row reports the observed best PDF page and normalized image error.
"""
from __future__ import annotations
import io
import json
import math
import shutil
import subprocess
from pathlib import Path
import pymupdf as fitz
from PIL import Image, ImageChops, ImageStat
from microgen_source_safe_orchestrator import read_json,digest,atomic_json,verify_workspace
from microgen_corrected_slide_clock import build_slide_clock

class SlidePixelAuditError(ValueError):
    pass

def _reference(page):
    scale=min(960/page.rect.width,540/page.rect.height)
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
    original=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
    canvas=Image.new("RGB",(960,540),"white")
    canvas.paste(original,((960-pix.width)//2,(540-pix.height)//2))
    return canvas.resize((320,180))

def _mean_abs(a,b):
    delta=ImageChops.difference(a,b)
    return sum(ImageStat.Stat(delta).mean)/3

def _samples(rows,total):
    points=[]
    for i,row in enumerate(rows,1):
        start,end=row["start"],row["end"]
        duration=end-start
        if duration<.1:
            raise SlidePixelAuditError("Slide too short for bounded pixel sampling")
        points.append((f"interior_{i:02d}",i,start+min(1.,duration*.35)))
        if i>1:
            previous=rows[i-2]
            # The proof bounds transitions to a half-second guard window.
            guard=min(.35,(previous["end"]-previous["start"])*.25,duration*.25)
            points.append((f"before_{i-1:02d}_{i:02d}",i-1,previous["end"]-guard))
            points.append((f"after_{i-1:02d}_{i:02d}",i,start+guard))
    tail=total-rows[-1]["end"]
    if tail<=0:raise SlidePixelAuditError("Verified original audio tail required")
    points.append(("final_audio_tail",17,total-min(.35,tail*.5)))
    if any(t<0 or t>=total for _,_,t in points):
        raise SlidePixelAuditError("Invalid page probe timestamp")
    return points

def audit_corrected_slide_pixels(stage,selection,shadow,candidate_dir,destination,*,ffmpeg,threshold=4.):
    source_plan=build_slide_clock(stage,selection,shadow)
    stage=Path(stage).resolve(strict=True)
    original=Path(source_plan["source"]["source_root"])
    video_dir=Path(candidate_dir).resolve(strict=True)
    dest=Path(destination).resolve(strict=False)
    protected=(stage,Path(selection).resolve(strict=True),
               Path(shadow).resolve(strict=True),video_dir,original)
    if (dest.exists() or dest.is_symlink() or
            any(dest==p or dest.is_relative_to(p) or p.is_relative_to(dest) for p in protected)):
        raise SlidePixelAuditError("Pixel audit must be isolated and new")
    if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0<threshold<=10:
        raise SlidePixelAuditError("Pixel threshold must be a conservative finite value")
    old=read_json(video_dir/"corrected_slide_clock_receipt.json")
    movie=video_dir/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4"
    pdf=original/"slides.pdf"
    if (movie.is_symlink() or not movie.is_file() or
            old.get("status")!="CORRECTED_SLIDE_CLOCK_NOT_SEMANTICALLY_APPROVED" or
            old.get("publication_allowed") is not False or
            old.get("word_highlights_present") is not False or
            old.get("video_sha256")!=digest(movie) or
            old.get("source_pdf_sha256")!=digest(pdf) or
            old.get("shadow_wav_sha256")!=digest(source_plan["shadow_wav"]) or
            old.get("slides")!=source_plan["segments"] or
            abs(old.get("audio_seconds",0)-source_plan["audio_seconds"])>.001):
        raise SlidePixelAuditError("Source PDF, video, PCM or current slide timing unbound")
    ff=Path(ffmpeg)
    if not ff.is_file() or ff.is_symlink():
        raise SlidePixelAuditError("Explicit regular ffmpeg executable required")
    with fitz.open(pdf) as document:
        if document.page_count!=17:raise SlidePixelAuditError("Original PDF count changed")
        references=[_reference(p) for p in document]
    probes=_samples(source_plan["segments"],source_plan["audio_seconds"])
    video_sha=digest(movie)
    pdf_sha=digest(pdf)
    dest.mkdir(parents=True,exist_ok=False)
    try:
        evidence=[]
        for name,expected,timestamp in probes:
            shot=dest/f"{name}.png"
            command=[str(ff),"-nostdin","-hide_banner","-loglevel","error",
                     "-y","-ss",f"{timestamp:.4f}","-i",str(movie),
                     "-frames:v","1",str(shot)]
            run=subprocess.run(command,capture_output=True,timeout=25)
            if run.returncode or not shot.is_file():
                raise SlidePixelAuditError("Cannot independently decode frame: "+
                      run.stderr.decode("utf8","replace")[-160:])
            with Image.open(shot) as f:
                actual=f.convert("RGB").resize((320,180))
            differences=[_mean_abs(actual,reference) for reference in references]
            best=min(range(17),key=lambda i:differences[i])+1
            expected_error=differences[expected-1]
            evidence.append({"sample":name,"expected_slide":expected,
                             "best_matching_pdf_slide":best,"time":round(timestamp,4),
                             "expected_mae":round(expected_error,4),
                             "best_mae":round(differences[best-1],4),
                             "correct_pdf_match":best==expected and expected_error<=threshold,
                             "frame_sha256":digest(shot)})
            shot.unlink()
        if digest(movie)!=video_sha or digest(pdf)!=pdf_sha or verify_workspace(stage)!=source_plan["source"]:
            raise SlidePixelAuditError("Input sources changed during image inspection")
        passed=all(row["correct_pdf_match"] for row in evidence)
        report={"status":"CORRECTED_SLIDE_PIXEL_AUDIT_PASS_NOT_ACADEMIC" if passed
                       else "CORRECTED_SLIDE_PIXEL_AUDIT_INCONCLUSIVE",
                "video_sha256":video_sha,"source_pdf_sha256":pdf_sha,
                "source_shadow_wav_sha256":old["shadow_wav_sha256"],
                "sample_count":len(evidence),"passed_samples":sum(x["correct_pdf_match"] for x in evidence),
                "samples":evidence,"guard_seconds":.35,
                "pixel_match_threshold":threshold,"slide_mapping_technically_verified":passed,
                "word_highlights_verified":False,"phonetic_verified":False,
                "mathematical_figure_semantics_verified":False,"publication_allowed":False}
        atomic_json(dest/"pixel_audit_receipt.json",report)
        return {"slide_pixel_pass":passed,"samples":len(evidence),
                "correct":report["passed_samples"],"report":str(dest/"pixel_audit_receipt.json"),
                "publication_allowed":False}
    except Exception:
        shutil.rmtree(dest)
        raise
