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
