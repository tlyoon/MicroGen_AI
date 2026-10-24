"""Rebuild exact slide order for corrected §2.5 narration, without old word cues.

Only timing from 17 verified *current* WAVs and source PDF is used.
Slide-level timing is a technical candidate, NOT verified element highlighting.
"""
from __future__ import annotations
import math
import subprocess
import shutil
import wave
from pathlib import Path
import pymupdf as fitz
from PIL import Image
from microgen_source_safe_orchestrator import verify_workspace,read_json,digest,atomic_json
from microgen_quality import check_video
from microgen_corrected_shadow_video import _pcm_properties
from microgen_audio_tail_video_candidate import _decoded_audio_hash

class CorrectedSlidesError(ValueError):
    pass

def build_slide_clock(corrected_stage,selection,shadow):
    stage=Path(corrected_stage).resolve(strict=True)
    sel=Path(selection).resolve(strict=True)
    sh=Path(shadow).resolve(strict=True)
    src=verify_workspace(stage)
    manifest=read_json(stage/"corrected_stage_receipt.json")
    select=read_json(sel/"selection_receipt.json")
    timeline=read_json(stage/"measured_timeline.json")
    aud=read_json(sh/"shadow_receipt.json")
    shadow_wav=sh/"section25_corrected_shadow_UNAPPROVED.wav"
    if (src["slide_count"]!=17 or
            manifest.get("status")!="SOURCE_BOUND_CORRECTED_AUDIO_NEEDS_NEW_ASR" or
            manifest.get("publication_allowed") is not False or
            manifest.get("fresh_offline_recognition_required") is not True or
            manifest.get("selection_receipt_sha256")!=digest(sel/"selection_receipt.json") or
            select.get("publication_allowed") is not False or
            aud.get("status")!="COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM" or
            aud.get("publication_allowed") is not False or
            aud.get("all_preexisting_ASR_cue_timing_invalidated") is not True or
            aud.get("corrected_slides")!=[5,6,10] or
            manifest.get("source_pdf_sha256")!=src["source_pdf_sha256"] or
            manifest.get("narration_sha256")!=src["narration_sha256"] or
            shadow_wav.is_symlink() or not shadow_wav.is_file() or
            aud.get("shadow_sha256")!=digest(shadow_wav)):
        raise CorrectedSlidesError("Corrected stage, source, selection or shadow mismatched")
    rows=timeline.get("slide_intervals")
    clips=manifest.get("actual_audio_bindings")
    if (not isinstance(rows,list) or len(rows)!=17 or
            not isinstance(clips,list) or len(clips)!=17):
        raise CorrectedSlidesError("Exactly 17 current slide durations required")
    positions=[]
    cursor=0.
    for i,(row,clip) in enumerate(zip(rows,clips),1):
        f=stage/"audio"/f"slide{i}.wav"
        if (row.get("slide")!=i or clip.get("slide")!=i or
                f.is_symlink() or not f.is_file() or
                row.get("wav_sha256")!=digest(f) or
                clip.get("sha256")!=digest(f)):
            raise CorrectedSlidesError("Current WAV identity differs from timing evidence")
        duration=row["end_seconds"]-row["start_seconds"]
        if (not math.isfinite(duration) or duration<=0.05 or
                abs(row["start_seconds"]-cursor)>.0001):
            raise CorrectedSlidesError("Noncontiguous measured slide clock")
        cursor=row["end_seconds"]
        positions.append({"slide":i,"start":row["start_seconds"],"end":row["end_seconds"],
                          "duration":round(duration,6),"wav_sha256":row["wav_sha256"]})
    tail=aud.get("tail_seconds")
    total=aud.get("audio_seconds")
    pcm=_pcm_properties(shadow_wav)
    if (type(tail) not in (int,float) or not math.isfinite(tail) or
            not .01<=tail<=3 or
            abs((cursor+tail)-total)>.01 or
            abs(pcm["pcm_seconds"]-total)>.01 or
            not 0<total<600):
        raise CorrectedSlidesError("Corrected shadow PCM and tail have inconsistent clocks")
    return {"segments":positions,"tail_seconds":tail,"audio_seconds":total,
            "pcm":pcm,"source":src,"stage":stage,"shadow_wav":shadow_wav}

def render_corrected_slide_clock(stage,selection,shadow,output,*,ffmpeg):
    plan=build_slide_clock(stage,selection,shadow)
    stage=plan["stage"];src=Path(plan["source"]["source_root"])
    dest=Path(output).resolve(strict=False)
    protect=(stage,Path(selection).resolve(strict=True),Path(shadow).resolve(strict=True),src)
    if (dest.exists() or dest.is_symlink() or
            any(dest==p or dest.is_relative_to(p) or p.is_relative_to(dest) for p in protect)):
        raise CorrectedSlidesError("Candidate must use brand-new independent directory")
    ff=Path(ffmpeg)
    if ff.is_symlink() or not ff.is_file():
        raise CorrectedSlidesError("Explicit installed FFmpeg required")
    pdf=src/"slides.pdf"
    sha=digest(pdf)
    dest.mkdir(parents=True,exist_ok=False)
    try:
        # Authoritative slide art is rasterized from SHA-bound original PDF
        # into newly owned temporary visual files; no historical PNG reuse.
        frames=[]
        with fitz.open(pdf) as document:
            if document.page_count!=17:raise CorrectedSlidesError("PDF page count changed")
            for row in plan["segments"]:
                i=row["slide"]
                page=document[i-1]
                scale=min(960/page.rect.width,540/page.rect.height)
                pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                actual=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
                canvas=Image.new("RGB",(960,540),"white")
                canvas.paste(actual,((960-pix.width)//2,(540-pix.height)//2))
                png=dest/f"slide{i:02d}.png"
                canvas.save(png)
                frames.append(png)
        if digest(pdf)!=sha:
            raise CorrectedSlidesError("Source PDF changed during frame generation")
        # The final extra line in concat is necessary to honor the last
        # still-image duration; the AAC overhang is assigned to slide 17.
        manifest=["ffconcat version 1.0"]
        for index,row in enumerate(plan["segments"]):
            manifest.extend((f"file '{frames[index].name}'",
                             f"duration {row['duration']:.6f}"))
        manifest.extend((f"file '{frames[-1].name}'",
                         f"duration {plan['tail_seconds']:.6f}",
                         f"file '{frames[-1].name}'"))
        movie_list=dest/"frames.ffconcat"
        movie_list.write_text("\n".join(manifest)+"\n",encoding="utf8")
        movie=dest/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4"
        command=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
                 "-f","concat","-safe","0","-i",str(movie_list),
                 "-i",str(plan["shadow_wav"]),"-map","0:v:0","-map","1:a:0",
                 "-vf","fps=8","-fps_mode","cfr",
                 "-c:v","libx264","-preset","ultrafast",
                 "-crf","28","-pix_fmt","yuv420p","-c:a","alac",
                 "-t",f"{plan['audio_seconds']:.6f}",
                 "-movflags","+faststart",str(movie)]
        result=subprocess.run(command,capture_output=True,timeout=240,cwd=dest)
        if result.returncode or not movie.is_file():
            raise CorrectedSlidesError("Slide-clock render failed: "+result.stderr.decode("utf8","replace")[-300:])
        info=check_video(movie,ffmpeg=str(ff))
        if not 0<info["seconds"]<600 or abs(info["seconds"]-plan["audio_seconds"])>.35:
            raise CorrectedSlidesError("Output duration differs from corrected narration")
        if _decoded_audio_hash(movie,ff)!=plan["pcm"]:
            raise CorrectedSlidesError("Video altered corrected audio PCM")
        if (digest(pdf)!=sha or
                digest(plan["shadow_wav"])!=read_json(Path(shadow)/"shadow_receipt.json")["shadow_sha256"] or
                verify_workspace(stage)!=plan["source"]):
            raise CorrectedSlidesError("Source changed during rendering")
        atomic_json(dest/"corrected_slide_clock_receipt.json",{
            "status":"CORRECTED_SLIDE_CLOCK_NOT_SEMANTICALLY_APPROVED",
            "source_pdf_sha256":sha,
            "video_sha256":digest(movie),"shadow_wav_sha256":digest(plan["shadow_wav"]),
            "slides":plan["segments"],"tail_seconds":plan["tail_seconds"],
            "audio_seconds":plan["audio_seconds"],"output_seconds":info["seconds"],
            "pcm_sha256_verified":plan["pcm"]["pcm_sha256"],
            "word_highlights_present":False,"slide_clock_pixel_verified":False,
            "phonetic_verified":False,"mathematical_figure_semantics_verified":False,
            "publication_allowed":False})
        return {"video":str(movie),"slide_count":17,
                "duration_seconds":info["seconds"],"pcm_verified":True,
                "slide_pixels_independently_verified":False,"publication_allowed":False}
    except Exception:
        shutil.rmtree(dest)
        raise
