"""Original MicroGen_AI lecture-production integration and isolated candidate tools.

Real slide geometry and measured WAV timing only; never infer spoken-word
alignment, verified phonetic correctness, mathematical QA or publishing approval.
No source mutation or paid services.
"""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
import pymupdf as fitz

class BridgeError(ValueError):
    pass

def _finite(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def _sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def inspect_lesson(directory):
    from microgen_quality import sha256
    stage=Path(directory)
    if stage.is_symlink() or not stage.is_dir():
        raise BridgeError("Existing regular lesson directory required")
    required=("slides.pdf","script_tts.json")
    for name in required:
        path=stage/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size<=0:
            raise BridgeError("Missing required lecture input "+name)
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf-8"))
    slides=data.get("slides",[])
    if not isinstance(slides,list) or not slides or len(slides)>500:
        raise BridgeError("Invalid narration slide inventory")
    if [r.get("slide") for r in slides]!=list(range(1,len(slides)+1)):
        raise BridgeError("Nonconsecutive narration slide IDs")
    with fitz.open(stage/"slides.pdf") as doc:
        count=doc.page_count
    if count!=len(slides):raise BridgeError("Narration/PDF page count mismatch")
    wavs=[stage/f"slide{i}.wav" for i in range(1,count+1)]
    has_audio=all(p.is_file() and not p.is_symlink() for p in wavs)
    return {"page_count":count,"slide_pdf_sha256":sha256(stage/"slides.pdf"),
       "narration_sha256":sha256(stage/"script_tts.json"),
       "complete_audio_set":has_audio,
       "production_ready":False,"source_modified":False}

def measured_wav_timeline(directory,slide_count):
    import wave
    stage=Path(directory)
    if type(slide_count) is not int or not 1<=slide_count<=500:
        raise BridgeError("Invalid slide count")
    elapsed=0.
    events=[]
    for i in range(1,slide_count+1):
        p=stage/f"slide{i}.wav"
        if p.is_symlink() or not p.is_file():raise BridgeError(f"Missing WAV {i}")
        try:
            with wave.open(str(p),"rb") as w:
                duration=w.getnframes()/w.getframerate()
        except (OSError,EOFError,ValueError,ZeroDivisionError) as exc:
            raise BridgeError("Unreadable lecture WAV") from exc
        if not math.isfinite(duration) or not .05<=duration<600:
            raise BridgeError("Invalid single-slide WAV timing")
        events.append({"slide":i,"start_seconds":round(elapsed,6),
           "end_seconds":round(elapsed+duration,6),"wav_sha256":_sha(p)})
        elapsed+=duration
    return {"schema_version":1,"slide_intervals":events,
            "duration_seconds":round(elapsed,6),
            "individual_word_times_verified":False}

def pdf_element_inventory(pdf):
    p=Path(pdf)
    if p.is_symlink() or not p.is_file():raise BridgeError("Original PDF required")
    result=[]
    with fitz.open(p) as doc:
        if not 1<=doc.page_count<=500:raise BridgeError("Unbounded slide PDF")
        for i,page in enumerate(doc,1):
            words=page.get_text("words")
            bbox=[]
            for word in words:
                x0,y0,x1,y1,txt=word[:5]
                if not all(math.isfinite(float(x)) for x in (x0,y0,x1,y1)):
                    raise BridgeError("Invalid element geometry")
                if not (0<=x0<x1<=page.rect.width+1 and 0<=y0<y1<=page.rect.height+1):
                    continue
                bbox.append({"text":txt,"box":[round(x0,3),round(y0,3),round(x1,3),round(y1,3)]})
            result.append({"slide":i,"width":page.rect.width,"height":page.rect.height,
                           "words":bbox,"source_geometry_extracted":True})
    return result

def validate_highlight_cues(cues,page_rows,timeline):
    if not isinstance(cues,list) or not 1<=len(cues)<=128:
        raise BridgeError("Explicit bounded highlight cues required")
    pages={x["slide"]:x for x in page_rows}
    intervals={x["slide"]:x for x in timeline["slide_intervals"]}
    seen=set();previous=(-1,0.)
    for c in cues:
        if not isinstance(c,dict) or set(c)!={"slide","text","box","start_seconds","end_seconds"}:
            raise BridgeError("Unexpected cue schema")
        i=c["slide"]
        if type(i) is not int or i not in pages or i not in intervals:
            raise BridgeError("Highlight cue slide not in input")
        box=c["box"]
        if (not isinstance(box,list) or len(box)!=4 or
            any(not _finite(x) for x in box) or
            not (0<=box[0]<box[2]<=pages[i]["width"]+1 and
                 0<=box[1]<box[3]<=pages[i]["height"]+1)):
            raise BridgeError("Invalid cue geometry")
        text=c["text"]
        matching=[word for word in pages[i]["words"] if word["text"]==text and
              all(abs(a-b)<2.0 for a,b in zip(box,word["box"]))]
        if not matching:raise BridgeError("No actual PDF text element matches cue")
        start,end=c["start_seconds"],c["end_seconds"]
        begin=intervals[i]["start_seconds"];finish=intervals[i]["end_seconds"]
        if not all(_finite(x) for x in (start,end)) or not begin<=start<end<=finish:
            raise BridgeError("Cue outside measured WAV interval")
        if (i,start)<previous or (i,start,end) in seen:
            raise BridgeError("Unordered or duplicate highlights")
        previous=(i,start);seen.add((i,start,end))
    return {"cue_geometry_validated":True,"cues":len(cues),
            "acoustic_word_alignment_verified":False}

def render_staged_highlight(pdf,wav,cues,output,*,ffmpeg_exe=None):
    """Draw cue rectangles only during their declared moments; no source overwrite."""
    import tempfile,subprocess,shutil,wave
    source=Path(pdf).resolve(strict=True);audio=Path(wav).resolve(strict=True)
    out=Path(output).resolve(strict=False)
    if out.exists() or out.is_symlink() or out.parent==source.parent or out.parent==audio.parent:
        raise BridgeError("Output must be new and outside source media directory")
    if source.suffix.lower()!=".pdf" or audio.suffix.lower()!=".wav":
        raise BridgeError("Original PDF/WAV types required")
    with wave.open(str(audio),"rb") as track:duration=track.getnframes()/track.getframerate()
    if not .05<=duration<570:raise BridgeError("Single segment outside duration budget")
    with fitz.open(source) as doc:
        if doc.page_count!=1:raise BridgeError("One-slide PDF required")
        page=doc[0];pw,ph=page.rect.width,page.rect.height
        if pw<=0 or ph<=0:raise BridgeError("Invalid PDF")
        with tempfile.TemporaryDirectory(prefix="microgen_overlay_") as temp:
            target=Path(temp)/"slide.png"
            pix=page.get_pixmap(matrix=fitz.Matrix(1280/pw,1280/pw),alpha=False)
            pix.save(str(target))
            scale=min(1280/pw,720/ph)
            offx=(1280-pw*scale)/2;offy=(720-ph*scale)/2
            filters=["scale=1280:720:force_original_aspect_ratio=decrease",
                     "pad=1280:720:(ow-iw)/2:(oh-ih)/2:white"]
            for cue in cues:
                start,end=cue["start_seconds"],cue["end_seconds"]
                box=cue["box"]
                if (not all(_finite(x) for x in (start,end,*box)) or
                    not 0<=start<end<=duration or
                    not 0<=box[0]<box[2]<=pw or not 0<=box[1]<box[3]<=ph):
                    raise BridgeError("Invalid overlay instruction")
                x=round(offx+box[0]*scale);y=round(offy+box[1]*scale)
                w=max(1,round((box[2]-box[0])*scale));h=max(1,round((box[3]-box[1])*scale))
                filters.append("drawbox=x=%d:y=%d:w=%d:h=%d:color=yellow@0.90:t=4:enable='between(t,%.5f,%.5f)'"%(x,y,w,h,start,end))
            from gen_video_v22 import ffmpeg_executable
            ffmpeg=ffmpeg_exe or ffmpeg_executable()
            if not ffmpeg:raise BridgeError("FFmpeg unavailable")
            cmd=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error","-y","-loop","1",
                 "-framerate","12","-i",str(target),"-i",str(audio),
                 "-t",f"{duration:.6f}","-vf",",".join(filters),
                 "-r","12","-c:v","libx264","-preset","ultrafast",
                 "-pix_fmt","yuv420p","-c:a","aac",str(out)]
            proc=subprocess.run(cmd,capture_output=True,timeout=120)
            if proc.returncode or not out.is_file():
                raise BridgeError("Staged FFmpeg highlight rendering failed: "+proc.stderr.decode("utf8","replace")[-400:])
    return {"candidate_mp4":str(out),"duration_seconds":duration,"cue_count":len(cues),
            "source_modified":False,"academic_accuracy_verified":False,
            "narration_sync_verified":False}

def preview_math_pronunciation(directory):
    from text_to_speech_v25 import normalize_scientific_speech
    data=json.loads((Path(directory)/"script_tts.json").read_text(encoding="utf8"))
    rows=[]
    for r in data["slides"]:
        original=str(r.get("tts_text") or r.get("narration") or "")
        if not original.strip():raise BridgeError("Empty narration source")
        spoken=normalize_scientific_speech(original)
        if not spoken.strip():raise BridgeError("Normalization erased narration")
        rows.append({"slide":r["slide"],"source_text_sha256":hashlib.sha256(original.encode()).hexdigest(),
           "spoken_input":spoken,"changed":spoken!=original})
    return {"normalization_preview":rows,"displayed_math_untouched":True,
            "tts_invoked":False,"spoken_phonemes_verified":False}

def candidate_tts_repair_plan(directory):
    original=Path(directory)
    plan=preview_math_pronunciation(original)
    changes=[row for row in plan["normalization_preview"] if row["changed"]]
    return {"schema_version":1,"proposed_corrections":[{"slide":x["slide"],
             "source_text_sha256":x["source_text_sha256"],"spoken_input":x["spoken_input"],
             "existing_wav_must_not_be_overwritten":True} for x in changes],
             "requires_consistent_voice":True,
             "provider_calls_made":0,"stage_only":True,"publication_allowed":False}

def pdf_layout_advisory(pdf,*,minimum_font_points=7.0):
    warnings=[]
    p=Path(pdf)
    if p.is_symlink() or not p.is_file():raise BridgeError("Original PDF missing")
    with fitz.open(p) as doc:
        for i,page in enumerate(doc,1):
            for item in page.get_text("dict")["blocks"]:
                if item.get("type")==0:
                    for line in item.get("lines",[]):
                        for span in line.get("spans",[]):
                            if span.get("text","").strip() and span.get("size",100)<minimum_font_points:
                                warnings.append({"slide":i,"kind":"SMALL_TEXT","text":span["text"][:60]})
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    if rect.is_empty or not page.rect.contains(rect):
                        warnings.append({"slide":i,"kind":"CLIPPED_IMAGE"})
                    elif rect.width/page.rect.width<.10:
                        warnings.append({"slide":i,"kind":"NARROW_IMAGE"})
    return {"layout_warnings":warnings,"academic_meaning_verified":False,
            "figures_modified":False,"source_modified":False}

def strict_slide_part_plan(timeline,*,ceiling=570.0):
    if not _finite(ceiling) or not 0<ceiling<600:
        raise BridgeError("Invalid strict video duration threshold")
    intervals=timeline.get("slide_intervals")
    if not isinstance(intervals,list) or not intervals:
        raise BridgeError("Source-bound audio intervals required")
    chunks=[];current=[];seconds=0.
    for item in intervals:
        duration=item["end_seconds"]-item["start_seconds"]
        if not _finite(duration) or duration<=0 or duration>=ceiling:
            raise BridgeError("Slide cannot be split without regenerating its narration")
        if current and seconds+duration>=ceiling:
            chunks.append({"slides":current,"planned_seconds":round(seconds,6)})
            current=[];seconds=0.
        current.append(item["slide"]);seconds+=duration
    if current:chunks.append({"slides":current,"planned_seconds":round(seconds,6)})
    if any(x["planned_seconds"]>=ceiling for x in chunks):
        raise BridgeError("Unsafe rounding in video part duration")
    return {"schema_version":1,"parts":chunks,
            "all_parts_strictly_under_600":True,
            "rendered_mp4s_verified":False,"narration_cuts_within_slide":False}
