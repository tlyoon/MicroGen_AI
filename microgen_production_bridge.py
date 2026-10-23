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
