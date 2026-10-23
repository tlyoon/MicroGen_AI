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

def recover_source_bound_wavs(source,stage,entries):
    """Manifest must bind every offered waveform to exactly the current slide text."""
    src=Path(source).resolve(strict=True)
    dest=_new_stage(src,stage)
    data=json.loads((src/"script_tts.json").read_text(encoding="utf8"))
    rows=data["slides"]; n=len(rows)
    if not isinstance(entries,list) or len(entries)!=n:
        raise CampaignError("Full explicit WAV inventory required")
    if sorted(x.get("slide") for x in entries)!=list(range(1,n+1)):
        raise CampaignError("Duplicate, missing, or extra audio slide")
    checked=[]
    for entry in sorted(entries,key=lambda e:e["slide"]):
        number=entry["slide"];origin=Path(entry["path"]).resolve(strict=True)
        expected=_tts_digest(rows[number-1])
        if (origin.suffix.lower()!=".wav" or origin.is_symlink() or
            not origin.is_file() or entry.get("narration_sha256")!=expected or
            entry.get("wav_sha256")!=_sha(origin)):
            raise CampaignError("Untrusted external WAV or narration binding")
        with wave.open(str(origin),"rb") as wav:
            length=wav.getnframes()/wav.getframerate()
        if not _finite(length) or not .05<=length<600:
            raise CampaignError("Invalid WAV evidence")
        checked.append((number,origin))
    # No staging side effects until every source has been verified.
    dest.mkdir(parents=True)
    try:
        for number,origin in checked:
            target=dest/f"slide{number}.wav"
            shutil.copyfile(origin,target)
            if _sha(target)!=_sha(origin):raise CampaignError("WAV changed in copy")
    except Exception:
        shutil.rmtree(dest)
        raise
    return {"audio_stage":str(dest),"slide_count":n,
            "source_bound":True,"source_modified":False}

def produce_spoken_inputs(source):
    from text_to_speech_v25 import normalize_scientific_speech
    p=Path(source)
    data=json.loads((p/"script_tts.json").read_text(encoding="utf8"))
    result=[]
    for index,row in enumerate(data["slides"],1):
        if row.get("slide")!=index:raise CampaignError("Unordered slide narration")
        raw=str(row.get("tts_text") or row.get("narration") or "")
        spoken=normalize_scientific_speech(raw)
        if not raw.strip() or not spoken.strip():
            raise CampaignError("Empty narration")
        result.append({"slide":index,"source_hash":hashlib.sha256(raw.encode()).hexdigest(),
            "speech_input_sha256":hashlib.sha256(spoken.encode()).hexdigest(),
            "speech_input":spoken,"changed":raw!=spoken})
    return {"slides":result,"provider_called":False,
            "phonetic_accuracy_established":False}

def regenerate_staged_wav(source,stage,slide,synthesize,*,voice="en-US-Chirp-HD-F",
                          provider="google_cloud_chirp3",attempts=3):
    src=Path(source).resolve(strict=True)
    dest=_new_stage(src,stage)
    inputs=produce_spoken_inputs(src)["slides"]
    if type(slide) is not int or not 1<=slide<=len(inputs):
        raise CampaignError("Invalid slide")
    if not callable(synthesize) or type(attempts) is not int or not 1<=attempts<=3:
        raise CampaignError("Invalid synthesis backend or retry bound")
    if not isinstance(voice,str) or not voice or not isinstance(provider,str) or not provider:
        raise CampaignError("Voice and provider must be pinned")
    dest.mkdir(parents=True)
    text=inputs[slide-1]["speech_input"]
    statuses=[]
    for attempt in range(1,attempts+1):
        output=dest/f"slide{slide}.attempt{attempt:02d}.wav"
        try:
            metadata=synthesize(text,output,voice=voice,provider=provider)
            if not isinstance(metadata,dict) or metadata.get("voice")!=voice or metadata.get("provider")!=provider:
                raise CampaignError("Mixed TTS voice or provider")
            if not output.is_file() or output.is_symlink():raise CampaignError("Missing generated WAV")
            with wave.open(str(output),"rb") as wav:
                seconds=wav.getnframes()/wav.getframerate()
            if not _finite(seconds) or not .05<=seconds<600:
                raise CampaignError("Invalid regenerated WAV duration")
            statuses.append({"attempt":attempt,"status":"STAGED","wav_sha256":_sha(output)})
            return {"status":"REVIEW_REQUIRED","slide":slide,"output":str(output),
                  "voice":voice,"provider":provider,"attempts":statuses,
                  "pronunciation_verified":False,"source_modified":False}
        except Exception as e:
            statuses.append({"attempt":attempt,"status":"FAILED","error_type":type(e).__name__})
            if output.exists() and not output.is_symlink():output.unlink()
    return {"status":"REGENERATION_FAILED","slide":slide,"attempts":statuses,
        "source_modified":False,"pronunciation_verified":False}
