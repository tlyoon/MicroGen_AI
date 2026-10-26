"""HP current-TTS two-part candidate highlighting, source- and audio-bound.

This renders real source-PDF word-bounding-box highlights from independently
recognized current slide WAVs. It does NOT certify figure/equation semantics,
pronunciation, narrator identity or allow public release.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw
from microgen_source_safe_orchestrator import atomic_json, digest, read_json
from microgen_quality import check_video
from microgen_fresh_source_cues import source_inventory

WIDTH,HEIGHT,FPS=640,360,8


class FreshHighlightError(ValueError):
    pass


def validate(stage,report_file,*,boundary=13):
    base,src=source_inventory(stage)
    if src["slide_count"]!=23 or boundary!=13:
        raise FreshHighlightError("Section 2.5 approved 13/10 split requires 23 slides")
    report=read_json(report_file)
    if (report.get("schema_version")!=1 or
        report.get("status")!="CURRENT_23_SLIDE_ASR_CANDIDATES_NOT_ACADEMIC_APPROVAL"
        or report.get("source")!=src or
        report.get("publication_allowed") is not False or
        report.get("phonetic_correctness_verified") is not False or
        report.get("figure_equation_alignment_verified") is not False):
        raise FreshHighlightError("Current ASR is not source-bound/unapproved")
    rows=report.get("slides")
    if not isinstance(rows,list) or len(rows)!=23:
        raise FreshHighlightError("Full 23 slides of observed words required")
    with fitz.open(base/"slides.pdf") as pdf:
        total=0
        for i,row in enumerate(rows,1):
            if (row.get("slide")!=i or
                row.get("wav_sha256")!=src["wav_inventory"][i-1]["wav_sha256"] or
                not isinstance(row.get("cues"),list)):
                raise FreshHighlightError("Cue slide or WAV SHA changed")
            page=pdf[i-1]
            for cue in row["cues"]:
                box=cue.get("box")
                if (not isinstance(box,list) or len(box)!=4 or
                    any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in box)
                    or not 0<=box[0]<box[2]<=page.rect.width+.1
                    or not 0<=box[1]<box[3]<=page.rect.height+.1
                    or not 0<=cue["start"]<cue["end"]<=
                    src["wav_inventory"][i-1]["duration_seconds"]+.02):
                    raise FreshHighlightError("Invalid PDF region or WAV clock")
                total+=1
        if total!=report["total_cues"] or total<10:
            raise FreshHighlightError("ASR candidate count mismatch/empty")
    return base,src,report


def _frames(base):
    with fitz.open(base/"slides.pdf") as pdf:
        result=[]
        for p in pdf:
            scale=min(WIDTH/p.rect.width,HEIGHT/p.rect.height)
            pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            im=Image.new("RGB",(WIDTH,HEIGHT),"white")
            off=((WIDTH-pix.width)//2,(HEIGHT-pix.height)//2)
            im.paste(Image.frombytes("RGB",(pix.width,pix.height),pix.samples),off)
            result.append((im,scale,off))
    return result


def _highlight(frame,scale,offset,items):
    if not items:return frame
    tint=Image.new("RGBA",frame.size,(0,0,0,0))
    paint=ImageDraw.Draw(tint)
    for cue in items:
        x0,y0,x1,y1=cue["box"]
        box=(round(x0*scale+offset[0]),round(y0*scale+offset[1]),
             round(x1*scale+offset[0]),round(y1*scale+offset[1]))
        paint.rectangle(box,fill=(255,189,45,90),outline=(243,70,18,255),width=2)
    return Image.alpha_composite(frame.convert("RGBA"),tint).convert("RGB")


def _concat_exact_wavs(stage,numbers,target):
    first=None;pcm=hashlib.sha256();duration=0.0
    with wave.open(str(target),"wb") as writer:
        for i in numbers:
            with wave.open(str(stage/f"slide{i}.wav"),"rb") as sound:
                opts=(sound.getnchannels(),sound.getsampwidth(),sound.getframerate())
                if opts!=(1,2,24000):
                    raise FreshHighlightError("Current HP TTS WAV format unexpectedly changed")
                if first is None:
                    first=opts;writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(24000)
                raw=sound.readframes(sound.getnframes())
                pcm.update(raw)
                writer.writeframes(raw)
                duration+=len(raw)/48000
    return duration,pcm.hexdigest()


def render_two_fresh_parts(stage,report_file,out,ffmpeg):
    base,source,report=validate(stage,report_file)
    target=Path(out).absolute()
    ff=Path(ffmpeg).resolve(strict=True)
    if (not ff.is_file() or ff.is_symlink() or target.is_symlink() or
        target.exists() or target==base or target.is_relative_to(base)
        or base.is_relative_to(target)):
        raise FreshHighlightError("Unmodified external output directory required")
    frames=_frames(base)
    old_report=digest(report_file)
    original_pdf=digest(base/"slides.pdf")
    target.mkdir(parents=True,exist_ok=False)
    result=[]
    try:
        for part,numbers in enumerate((list(range(1,14)),list(range(14,24))),1):
            audio=target/f"part{part:02d}.source_pcm.wav"
            seconds,audio_pcm=_concat_exact_wavs(base,numbers,audio)
            if not 60<seconds<570:
                raise FreshHighlightError("Unsafe part clock (>=570s or implausibly short)")
            mp4=target/f"part{part:02d}_WORD_CUES_UNAPPROVED.mp4"
            command=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
                     "-f","rawvideo","-pixel_format","rgb24",
                     "-video_size",f"{WIDTH}x{HEIGHT}","-framerate",str(FPS),
                     "-i","pipe:0","-i",str(audio),"-map","0:v:0","-map","1:a:0",
                     "-c:v","libx264","-preset","ultrafast","-crf","25",
                     "-pix_fmt","yuv420p","-c:a","alac","-t",f"{seconds:.6f}",
                     "-movflags","+faststart",str(mp4)]
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,
                                  stderr=subprocess.PIPE,stdout=subprocess.DEVNULL)
            count=math.ceil(seconds*FPS)
            current=0;segment_start=0.0;cache={};active=0
            try:
                for tick in range(count):
                    time=(tick+.5)/FPS
                    while current<len(numbers)-1 and time>=segment_start+source["wav_inventory"][numbers[current]-1]["duration_seconds"]:
                        segment_start+=source["wav_inventory"][numbers[current]-1]["duration_seconds"]
                        current+=1
                    slide=numbers[current]
                    candidates=report["slides"][slide-1]["cues"]
                    offset=time-segment_start
                    on=tuple(j for j,c in enumerate(candidates)
                             if c["start"]<=offset<c["end"])
                    key=(slide,on)
                    if key not in cache:
                        frame,scale,pos=frames[slide-1]
                        cache[key]=_highlight(frame,scale,pos,[candidates[j] for j in on])
                    if on:active+=1
                    proc.stdin.write(cache[key].tobytes())
                proc.stdin.close()
                rc=proc.wait(timeout=300)
                error=proc.stderr.read().decode("utf8","replace")
                proc.stderr.close()
                if rc!=0 or not mp4.is_file():
                    raise FreshHighlightError("FFmpeg highlighted render error "+error[-400:])
            finally:
                if proc.poll() is None:
                    proc.kill();proc.wait(timeout=10)
            info=check_video(mp4,ffmpeg=str(ff),expected_seconds=seconds)
            if info["seconds"]>=600:
                raise FreshHighlightError("Actual encoded video violates 10-minute policy")
            result.append({"part":part,"slides":[numbers[0],numbers[-1]],
                           "raw_audio_pcm_sha256":audio_pcm,
                           "input_wav_sha256":[source["wav_inventory"][i-1]["wav_sha256"] for i in numbers],
                           "video_sha256":digest(mp4),"video_file":mp4.name,
                           "audio_file":audio.name,"seconds":info["seconds"],
                           "active_cue_frames":active,"total_frames":count})
            print("HIGHLIGHTED_PART",part,"SECONDS",round(info["seconds"],3),
                  "FRAMES",count,"ACTIVE",active,flush=True)
        if digest(report_file)!=old_report or digest(base/"slides.pdf")!=original_pdf:
            raise FreshHighlightError("Source evidence changed while rendering")
        if source_inventory(base)[1]!=source:
            raise FreshHighlightError("WAVs changed during render")
        receipt={"status":"TWO_HIGHLIGHTED_WORD_CANDIDATES_NOT_PUBLICATION_APPROVAL",
                 "schema_version":1,"source":source,
                 "cue_report_sha256":old_report,"source_pdf_sha256":original_pdf,
                 "parts":result,"word_pixel_independently_verified":False,
                 "spoken_equation_figure_semantics_verified":False,
                 "phonetic_correctness_verified":False,"publication_allowed":False}
        atomic_json(target/"highlighted_part_receipt.json",receipt)
        return {"parts":len(result),"frames":sum(x["total_frames"] for x in result),
                "candidate_cues":report["total_cues"],"publication_allowed":False}
    except Exception:
        shutil.rmtree(target)
        raise


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True);p.add_argument("--cues",required=True)
    p.add_argument("--output",required=True);p.add_argument("--ffmpeg",required=True)
    a=p.parse_args()
    print(json.dumps(render_two_fresh_parts(a.stage,a.cues,a.output,a.ffmpeg)))
