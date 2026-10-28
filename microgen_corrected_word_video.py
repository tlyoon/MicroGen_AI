"""Safe offline 17-slide corrected candidate with current SHA-bound word overlays.

Stream PDF-derived frames rather than reusing outdated historical cue clocks.
Visual highlights are *candidate* ASR word-to-PDF matches, not evidence of
pronunciation, mathematical meaning, figure correctness or publication.
"""
from __future__ import annotations
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw

from microgen_source_safe_orchestrator import atomic_json, digest, read_json, verify_workspace
from microgen_audio_cue_binding import validate_audio_bound_cues, _verified_audio_rows
from microgen_corrected_slide_clock import build_slide_clock
from microgen_audio_tail_video_candidate import _decoded_audio_hash
from microgen_quality import check_video

class CorrectedHighlightError(ValueError):
    pass

WIDTH, HEIGHT, FPS = 960, 540, 8


def _validated_inputs(stage, selection, shadow, asr):
    stage=Path(stage).resolve(strict=True)
    plan=build_slide_clock(stage,selection,shadow)
    cues_path=stage/"cues.json"
    if cues_path.is_symlink() or not cues_path.is_file():
        raise CorrectedHighlightError("Fresh current corrected cue file required")
    cues=read_json(cues_path)
    validate_audio_bound_cues(stage,cues)
    if (cues.get("derivation")!="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH"
            or cues.get("publication_allowed") is not False
            or cues.get("spoken_word_alignment_verified") is not False
            or cues.get("mathematics_semantics_verified") is not False):
        raise CorrectedHighlightError("Only new unapproved corrected-ASR cues permitted")
    report=read_json(asr)
    src, audio, _=_verified_audio_rows(stage)
    if (report.get("schema_version")!=1
            or report.get("status")!="CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH"
            or report.get("publication_allowed") is not False
            or report.get("phonetic_identity_verified") is not False
            or report.get("semantic_alignment_verified") is not False
            or report.get("source_pdf_sha256")!=src["source_pdf_sha256"]
            or report.get("narration_sha256")!=src["narration_sha256"]
            or report.get("stage_audio_bindings")!=audio
            or len(report.get("results",[]))!=17):
        raise CorrectedHighlightError("Recognition provenance does not match current audio")
    items=cues.get("elements")
    if not isinstance(items,list) or not 1<=len(items)<=300:
        raise CorrectedHighlightError("Bounded nonempty fresh cues required")
    grouped={i:[] for i in range(1,18)}
    for index,item in enumerate(items):
        slide=item["slide"]
        grouped[slide].append({"id":index,"start":item["start_seconds"],
                               "end":item["end_seconds"],"box":item["box"]})
    return plan,cues_path,grouped,len(items)


def _pdf_frames(source):
    original=Path(source)/"slides.pdf"
    sha=digest(original)
    frames=[]
    transforms=[]
    with fitz.open(original) as pdf:
        if pdf.page_count!=17:raise CorrectedHighlightError("Original PDF page count changed")
        for page in pdf:
            scale=min(WIDTH/page.rect.width,HEIGHT/page.rect.height)
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            frame=Image.new("RGB",(WIDTH,HEIGHT),"white")
            frame.paste(Image.frombytes("RGB",(pix.width,pix.height),pix.samples),
                        ((WIDTH-pix.width)//2,(HEIGHT-pix.height)//2))
            frames.append(frame)
            transforms.append((scale,(WIDTH-pix.width)//2,(HEIGHT-pix.height)//2))
    if digest(original)!=sha:raise CorrectedHighlightError("Original PDF changed during decode")
    return sha,frames,transforms


def _highlight(frame,transform,items):
    if not items:return frame
    scale,offset_x,offset_y=transform
    tint=Image.new("RGBA",frame.size,(0,0,0,0))
    draw=ImageDraw.Draw(tint)
    for item in items:
        x0,y0,x1,y1=item["box"]
        box=(round(x0*scale+offset_x),round(y0*scale+offset_y),
             round(x1*scale+offset_x),round(y1*scale+offset_y))
        draw.rectangle(box,fill=(255,198,60,75),outline=(240,85,20,220),width=3)
    return Image.alpha_composite(frame.convert("RGBA"),tint).convert("RGB")


def render_corrected_word_highlight_candidate(stage,selection,shadow,asr,destination,*,ffmpeg):
    plan,cues_path,grouped,total_cues=_validated_inputs(stage,selection,shadow,asr)
    base=plan["stage"]
    source=Path(plan["source"]["source_root"]).resolve(strict=True)
    output=Path(destination).resolve(strict=False)
    protected=(base,source,Path(selection).resolve(strict=True),
               Path(shadow).resolve(strict=True),Path(asr).resolve(strict=True).parent)
    if (output.exists() or output.is_symlink() or
            any(output==p or output.is_relative_to(p) or p.is_relative_to(output)
                for p in protected)):
        raise CorrectedHighlightError("Output must be a new independent review folder")
    ff=Path(ffmpeg).resolve(strict=True)
    if not ff.is_file() or ff.is_symlink():
        raise CorrectedHighlightError("Explicit installed FFmpeg required")
    cues_sha=digest(cues_path)
    asr_sha=digest(asr)
    pdf_sha,frames,transforms=_pdf_frames(source)
    seconds=plan["audio_seconds"]
    if not 0<seconds<600:raise CorrectedHighlightError("Lecture time bound invalid")
    count=math.ceil(seconds*FPS)
    if not 1<count<=4800:raise CorrectedHighlightError("Unsafe video frame count")
    output.mkdir(parents=True,exist_ok=False)
    video=output/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4"
    command=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
             "-f","rawvideo","-pixel_format","rgb24",
             "-video_size",f"{WIDTH}x{HEIGHT}","-framerate",str(FPS),
             "-i","pipe:0","-i",str(plan["shadow_wav"]),
             "-map","0:v:0","-map","1:a:0","-c:v","libx264",
             "-preset","ultrafast","-crf","28","-pix_fmt","yuv420p",
             "-c:a","alac","-t",f"{seconds:.6f}",
             "-movflags","+faststart",str(video)]
    process=None
    rendered_frames=0
    active_frames=0
    try:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        step=0
        cached={}
        segment=0
        for index in range(count):
            t=(index+.5)/FPS
            while segment<16 and t>=plan["segments"][segment]["end"]:
                segment+=1
            slide=segment+1
            on=tuple(row["id"] for row in grouped[slide]
                     if row["start"]<=t<row["end"])
            key=(slide,on)
            if key not in cached:
                rows=[r for r in grouped[slide] if r["id"] in on]
                cached[key]=_highlight(frames[segment],transforms[segment],rows)
            if on:active_frames+=1
            process.stdin.write(cached[key].tobytes())
            rendered_frames+=1
        process.stdin.close()
        rc=process.wait(timeout=240)
        error=process.stderr.read().decode("utf8","replace")
        process.stderr.close()
        if rc!=0 or not video.is_file():
            raise CorrectedHighlightError("FFmpeg highlighted render failed: "+error[-350:])
        actual=check_video(video,ffmpeg=str(ff))["seconds"]
        if not 0<actual<600 or abs(actual-seconds)>.3:
            raise CorrectedHighlightError("Highlighted render duration is not corrected PCM duration")
        if _decoded_audio_hash(video,ff)!=plan["pcm"]:
            raise CorrectedHighlightError("Exact corrected PCM mismatch in highlighted MP4")
        if (digest(cues_path)!=cues_sha or digest(asr)!=asr_sha
                or digest(source/"slides.pdf")!=pdf_sha
                or digest(plan["shadow_wav"])!=read_json(Path(shadow)/"shadow_receipt.json")["shadow_sha256"]
                or verify_workspace(base)!=plan["source"]):
            raise CorrectedHighlightError("Source or cue bytes changed while rendering")
        receipt={"status":"ASR_WORD_HIGHLIGHT_TECHNICAL_CANDIDATE_NOT_APPROVED",
                 "video_sha256":digest(video),"source_pdf_sha256":pdf_sha,
                 "recognition_report_sha256":asr_sha,"cue_manifest_sha256":cues_sha,
                 "shadow_wav_sha256":digest(plan["shadow_wav"]),
                 "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
                 "duration_seconds":actual,"slide_count":17,"candidate_cues":total_cues,
                 "frames_rendered":rendered_frames,"frames_with_cues":active_frames,
                 "fps":FPS,"audio_pcm_identical":True,
                 "word_highlight_pixels_independently_verified":False,
                 "phonetic_correctness_verified":False,
                 "mathematical_figure_semantics_verified":False,
                 "voice_consistency_verified":False,"publication_allowed":False}
        atomic_json(output/"word_highlight_candidate_receipt.json",receipt)
        return {"video":str(video),"candidate_cues":total_cues,
                "duration_seconds":actual,"frames_with_cues":active_frames,
                "pcm_verified":True,"publication_allowed":False}
    except Exception:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        shutil.rmtree(output)
        raise
