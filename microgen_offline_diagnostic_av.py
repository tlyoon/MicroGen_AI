"""Offline FFmpeg A/V demonstration for source-bound teaching slides.

Accepts pre-existing locally synthesized DIAGNOSTIC WAVs only. Never selects
a formal narrator, performs TTS, modifies original textbook assets, or
confuses a mux smoke test with an academically verified lecture.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageChops, ImageStat
from microgen_pronunciation_closed_loop import sha_file


class OfflineDemoError(ValueError):
    pass


def inspect_inputs(slides_dir:Path, narration_qa:Path, diagnostic_wav_dir:Path,
                   *, declared_diagnostic_voice:str)->dict:
    slides_dir=Path(slides_dir);narration_qa=Path(narration_qa)
    diagnostic_wav_dir=Path(diagnostic_wav_dir)
    if (slides_dir.is_symlink() or not slides_dir.is_dir()
        or diagnostic_wav_dir.is_symlink() or not diagnostic_wav_dir.is_dir()
        or narration_qa.is_symlink() or not narration_qa.is_file()):
        raise OfflineDemoError("Independent slide, narration and diagnostic WAV evidence required")
    if (not isinstance(declared_diagnostic_voice,str) or
        not declared_diagnostic_voice.strip() or len(declared_diagnostic_voice)>90):
        raise OfflineDemoError("Explicit LOCAL diagnostic voice declaration required")
    pdf=slides_dir/"slides_teaching_candidate.pdf"
    manifest=slides_dir/"teaching_slide_receipt.json"
    if any(p.is_symlink() or not p.is_file() for p in (pdf,manifest)):
        raise OfflineDemoError("Source-bound rendered slides missing")
    m=json.loads(manifest.read_text(encoding="utf8"))
    n=json.loads(narration_qa.read_text(encoding="utf8"))
    if (m.get("status") not in (
            "FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED",
            "EXPANDED_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED")
        or m.get("rendered_pdf_sha256")!=sha_file(pdf)
        or m.get("narration_qa_sha256")!=sha_file(narration_qa)
        or m.get("publication_allowed") is not False
        or m.get("formal_voice_authorized") is not False
        or n.get("publication_allowed") is not False
        or n.get("formal_voice_authorized") is not False
        or len(m.get("slides",[]))!=m.get("slide_count")
        or len(n.get("slides",[]))!=m.get("slide_count")):
        raise OfflineDemoError("Wrong or falsely approved source-to-narration receipt")
    count=m["slide_count"]
    if not 1<=count<=20:raise OfflineDemoError("Diagnostic video length budget exceeded")
    items=[]
    total=0.
    with fitz.open(pdf) as pages:
        if len(pages)!=count:raise OfflineDemoError("Rendered slide count does not match receipt")
        for i,(v,s) in enumerate(zip(m["slides"],n["slides"]),1):
            if (v.get("slide")!=i or s.get("slide")!=i or
                v.get("narration_sha256")!=s.get("spoken_text_sha256")):
                raise OfflineDemoError("Narration/visual slide identity mismatch")
            source=diagnostic_wav_dir/f"slide{i:02d}.wav"
            if source.is_symlink() or not source.is_file():
                raise OfflineDemoError("Diagnostic WAV missing or unsafe")
            with wave.open(str(source),"rb") as w:
                if (w.getnchannels()!=1 or w.getsampwidth()!=2 or
                    w.getcomptype()!="NONE" or w.getframerate()<8000 or
                    w.getframerate()>96000 or w.getnframes()<=0):
                    raise OfflineDemoError("Require nonempty mono signed PCM16 diagnostic WAV")
                duration=w.getnframes()/w.getframerate()
                if duration>.0+180 or duration<.2:
                    raise OfflineDemoError("Per-slide WAV duration budget exceeded")
            if (abs(pages[i-1].rect.width/pages[i-1].rect.height-16/9)>.02):
                raise OfflineDemoError("Invalid video source aspect ratio")
            total+=duration
            items.append({"slide":i,"wav_sha256":sha_file(source),
                          "wav_filename":source.name,"seconds":round(duration,4),
                          "narration_text_sha256":s["spoken_text_sha256"]})
    if total>1800:raise OfflineDemoError("Total A/V demonstration budget exceeded")
    return {"schema_version":1,
        "status":"DIAGNOSTIC_VOICE_NOT_FORMAL_TTS_OR_ACADEMIC_QA",
        "rendered_pdf_sha256":sha_file(pdf),
        "rendered_manifest_sha256":sha_file(manifest),
        "narration_qa_sha256":sha_file(narration_qa),
        "declared_diagnostic_voice":declared_diagnostic_voice,
        "diagnostic_voice_identity_cryptographically_verified":False,
        "slide_count":count,"total_input_audio_seconds":round(total,4),
        "slides":items,"voice_is_formal":False,
        "academic_audio_quality_verified":False,
        "technical_word_pronunciation_verified":False,
        "provider_calls":0,"production_wavs_generated":False,
        "publication_allowed":False}


def build_demo_video(slides_dir:Path,narration_qa:Path,diagnostic_wav_dir:Path,
                     new_output:Path,*,declared_diagnostic_voice:str,
                     ffmpeg_bin:str="ffmpeg",ffprobe_bin:str="ffprobe")->dict:
    record=inspect_inputs(slides_dir,narration_qa,diagnostic_wav_dir,
                          declared_diagnostic_voice=declared_diagnostic_voice)
    output=Path(new_output).resolve(strict=False)
    stage=Path(slides_dir).resolve(strict=True)
    audio=Path(diagnostic_wav_dir).resolve(strict=True)
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
        or stage==output or stage in output.parents
        or audio==output or audio in output.parents
        or any(x.casefold()=="my drive" for x in output.parts)):
        raise OfflineDemoError("Fresh external audio/video demo required")
    if shutil.which(ffmpeg_bin) is None or shutil.which(ffprobe_bin) is None:
        raise OfflineDemoError("Offline ffmpeg and ffprobe executable required")
    temp=Path(tempfile.mkdtemp(prefix=".microgen-diagnostic-av-pending-",
                               dir=output.parent))
    try:
        files=[]
        with fitz.open(stage/"slides_teaching_candidate.pdf") as pdf:
            for entry in record["slides"]:
                num=entry["slide"]
                img=temp/f"slide_{num:02d}.png"
                pdf[num-1].get_pixmap(alpha=False).save(str(img))
                seg=temp/f"segment_{num:02d}.mp4"
                audiofile=audio/entry["wav_filename"]
                cmd=[ffmpeg_bin,"-hide_banner","-loglevel","error","-nostdin","-n",
                     "-loop","1","-framerate","1","-i",str(img),"-i",str(audiofile),
                     "-c:v","libx264","-preset","ultrafast","-tune","stillimage",
                     "-pix_fmt","yuv420p","-r","1",
                     "-c:a","aac","-b:a","96k","-t",f"{entry['seconds']:.4f}",str(seg)]
                subprocess.run(cmd,check=True,timeout=180,
                               stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                files.append(seg)
        concat=temp/"segments.ffconcat"
        concat.write_text("ffconcat version 1.0\n"+"".join(
            "file '"+p.name+"'\n" for p in files),encoding="utf8")
        result=temp/"lecture_diagnostic_only.mp4"
        subprocess.run([ffmpeg_bin,"-hide_banner","-loglevel","error","-nostdin","-n",
                        "-safe","0","-f","concat","-i",str(concat),
                        "-c","copy","-movflags","+faststart",str(result)],
                       check=True,timeout=180,stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)
        probe=subprocess.run([ffprobe_bin,"-v","error",
            "-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1",str(result)],
            capture_output=True,text=True,check=True,timeout=30)
        actual=float(probe.stdout.strip())
        streams=subprocess.run([ffprobe_bin,"-v","error","-show_entries",
            "stream=codec_type","-of","json",str(result)],capture_output=True,
            text=True,check=True,timeout=30)
        codec_types={x.get("codec_type") for x in json.loads(streams.stdout).get("streams",[])}
        if not {"audio","video"}.issubset(codec_types):
            raise OfflineDemoError("Diagnostic MP4 must retain actual audio and video streams")
        if abs(actual-record["total_input_audio_seconds"])>max(2.0,record["total_input_audio_seconds"]*.02):
            raise OfflineDemoError("MP4/WAV total duration drift exceeds two-percent limit")
        # Confirm that each actual MP4 time section displays its intended PDF
        # slide; a successful mux and duration alone do not prove sequencing.
        frame_alignment=[]
        elapsed=0.0
        for entry in record["slides"]:
            midpoint=elapsed+entry["seconds"]*.5
            probe_frame=temp/f"verified_frame_{entry['slide']:02d}.png"
            subprocess.run([ffmpeg_bin,"-hide_banner","-loglevel","error",
                            "-nostdin","-ss",f"{midpoint:.3f}",
                            "-i",str(result),"-frames:v","1","-n",str(probe_frame)],
                           check=True,timeout=40,stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE)
            with Image.open(probe_frame) as observed, Image.open(
                    temp/f"slide_{entry['slide']:02d}.png") as reference:
                if observed.size!=reference.size:
                    raise OfflineDemoError("Rendered video frame dimensions drifted")
                difference=ImageChops.difference(observed.convert("RGB"),
                                                 reference.convert("RGB"))
                fraction=sum(ImageStat.Stat(difference).mean)/(3*255)
                if fraction>.08:
                    raise OfflineDemoError("MP4 time location shows wrong slide or visible corruption")
                frame_alignment.append({
                    "slide":entry["slide"],"approximate_midpoint_seconds":round(midpoint,3),
                    "mean_absolute_rgb_fraction":round(fraction,6),
                    "matches_original_slide_under_8pct_threshold":True})
            elapsed+=entry["seconds"]
        if any(sha_file(audio/row["wav_filename"])!=row["wav_sha256"]
               for row in record["slides"]):
            raise OfflineDemoError("Diagnostic WAV modified during video composition")
        if sha_file(stage/"slides_teaching_candidate.pdf")!=record["rendered_pdf_sha256"]:
            raise OfflineDemoError("Original teaching-slide PDF changed")
        record.update({"status":"DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION",
            "video_slide_frame_alignment":frame_alignment,
            "all_slide_midpoints_source_pixel_checked":True,
            "diagnostic_mp4_sha256":sha_file(result),
            "diagnostic_mp4_duration_seconds":round(actual,3),
            "formal_voice_authorized":False,
            "academic_publication_ready":False})
        (temp/"diagnostic_av_receipt.json").write_text(
            json.dumps(record,indent=2),encoding="utf8")
        if output.exists():raise OfflineDemoError("Output appeared before finalization")
        os.rename(temp,output)
        return record
    finally:
        if temp.exists():shutil.rmtree(temp)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--slides",type=Path,required=True)
    p.add_argument("--narration-qa",type=Path,required=True)
    p.add_argument("--diagnostic-wavs",type=Path,required=True)
    p.add_argument("--voice",required=True)
    p.add_argument("--new-dir",type=Path,required=True)
    a=p.parse_args(argv)
    out=build_demo_video(a.slides,a.narration_qa,a.diagnostic_wavs,
                         a.new_dir,declared_diagnostic_voice=a.voice)
    print(json.dumps({"directory":str(a.new_dir),
        "mp4_seconds":out["diagnostic_mp4_duration_seconds"],
        "slide_count":out["slide_count"],"voice_is_formal":False,
        "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
