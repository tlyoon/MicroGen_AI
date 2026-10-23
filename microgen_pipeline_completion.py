"""Source-safe integration pieces for original MicroGen_AI production workflow.

Physical source WAV/slide evidence and staged outputs only. No background
generation, no paid calls, no Whisper, no publication, and no false
phonetic/word-level synchronization or mathematics verification.
"""
from __future__ import annotations
import hashlib,json,math,re,shutil,subprocess,tempfile,wave
from pathlib import Path
import pymupdf as fitz
from microgen_production_bridge import BridgeError,measured_wav_timeline as _timeline

class CampaignError(ValueError):
    pass

def _finite(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def _sha(file):
    sha=hashlib.sha256()
    with Path(file).open("rb") as f:
        for chunk in iter(lambda:f.read(2**20),b""):sha.update(chunk)
    return sha.hexdigest()

def _tts_digest(item):
    text=str(item.get("tts_text") or item.get("narration") or "")
    if not text.strip():raise CampaignError("Empty source narration")
    return hashlib.sha256(text.encode("utf8")).hexdigest()

def _new_stage(source,destination):
    source=Path(source).resolve(strict=True)
    dest=Path(destination).resolve(strict=False)
    if (dest==source or source in dest.parents or dest in source.parents or
        dest.exists() or dest.is_symlink()):
        raise CampaignError("Stage must be a new independent directory outside source")
    return dest

def production_contract(source):
    from microgen_production_bridge import inspect_lesson
    p=Path(source)
    evidence=inspect_lesson(p)
    n=evidence["page_count"]
    return {"schema_version":1,"source_root":str(p.resolve()),
       "source_pdf_sha256":evidence["slide_pdf_sha256"],
       "narration_sha256":evidence["narration_sha256"],
       "slide_count":n,"source_audio_complete":evidence["complete_audio_set"],
       "next_action":"PLAN_AND_STAGE" if evidence["complete_audio_set"] else "RECOVER_OR_SYNTHESIZE_MISSING_AUDIO",
       "source_modified":False,"ready_for_publication":False}
