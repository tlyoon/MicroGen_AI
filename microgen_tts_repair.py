"""Bounded repair attempts for pre-reviewed TTS pronunciations, stage-only.

Existing lecture sources and WAVs are NEVER replaced here. Synthesizer is a
callable supplied by the normal TTS provider, not an API dependency.
A successful waveform is only a review candidate until acoustic evidence,
academic review, and human listening are independently signed off.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Callable

from microgen_tts_provenance import digest_file, wav_characteristics
from microgen_tts_lexicon import verify_spoken_rules
from microgen_tts_wave_integrity import require_structurally_usable_audio,WaveIntegrityError

class RepairError(RuntimeError):
    pass

def authorized_slides(register:dict) -> list[int]:
    """Only slides for which *every* risk has a reviewed automatic correction."""
    if register.get("schema_version")!=1 or not isinstance(register.get("slides"),list):
        raise RepairError("Untrusted pronunciation register")
    allowed=[]
    for row in register["slides"]:
        risk=row.get("risks",[])
        if not risk:
            continue
        if all(x.get("automatic_text_correction") is True and
               x.get("expected_spoken") for x in risk):
            allowed.append(row["slide"])
    return allowed

def stage_repair(
    stage:Path, register:dict, slide:int, new_stage:Path,
    synthesize:Callable[[str,Path],str],
    normalize:Callable[[str],str],
    *, provider:str="google_cloud_chirp3", voice:str="en-US-Chirp-HD-F",
    rate:float=0.8, max_attempts:int=2,
    acoustic_gate:Callable[[Path,str],str] | None=None,
) -> dict:
    """Make candidate WAV(s); acoustic_gate returns 'clear', 'defect', 'unknown'.

    The gate must analyze actual candidate WAVs. A 'clear' diagnostic is NOT
    a human listening approval and never authorizes production promotion.
    """
    stage=Path(stage);new_stage=Path(new_stage)
    if max_attempts not in (1,2,3):
        raise RepairError("Attempt cap must be 1 to 3")
    if not isinstance(slide,int) or slide not in authorized_slides(register):
        raise RepairError("Slide has no fully reviewed automatic repair rule")
    if new_stage.exists() or new_stage.is_symlink() or new_stage==stage:
        raise RepairError("Refusing existing or production output directory")
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise RepairError("Unexpected source slide order")
    if register.get("slide_count")!=len(slides):
        raise RepairError("Register and script mismatch")
    row=register["slides"][slide-1]
    if row.get("slide")!=slide:
        raise RepairError("Register slide mismatch")
    raw=str(slides[slide-1].get("tts_text") or slides[slide-1].get("narration") or "")
    spoken=normalize(raw)
    if hashlib.sha256(raw.encode("utf8")).hexdigest()!=row.get("tts_source_sha256"):
        raise RepairError("Source narration SHA drift")
    if hashlib.sha256(spoken.encode("utf8")).hexdigest()!=row.get("spoken_input_sha256"):
        raise RepairError("Normalized speech SHA drift")
    old=stage/f"slide{slide}.wav"
    if digest_file(old)!=row.get("audio_wav_sha256"):
        raise RepairError("Original WAV SHA drift")
    if verify_spoken_rules(raw,spoken):
        raise RepairError("Known pronunciation lexicon rule not satisfied")
    if provider!="google_cloud_chirp3" or not voice or rate<=0:
        raise RepairError("Provider/voice/rate not pinned")
    new_stage.mkdir(parents=True)
    attempts=[]
    for count in range(1,max_attempts+1):
        target=new_stage/f"slide{slide}.attempt{count:02}.wav"
        try:
            returned=synthesize(spoken,target)
            if returned!=provider:
                raise RepairError("Mixed/unexpected TTS provider")
            if not target.is_file():
                raise RepairError("No candidate audio generated")
            characteristics=wav_characteristics(target)
            if characteristics["duration_seconds"]<=0:
                raise RepairError("Empty WAV")
            wave_report=require_structurally_usable_audio(target)
            result=acoustic_gate(target,spoken) if acoustic_gate is not None else "unknown"
            if result not in ("clear","defect","unknown"):
                raise RepairError("Invalid acoustic diagnostic status")
            attempts.append({
                "attempt":count, "provider":returned, "voice":voice,
                "speaking_rate":rate,"wav_sha256":digest_file(target),
                "wav_properties":characteristics,"pcm_integrity":wave_report,
                "acoustic_assessment":result,
                "file":target.name,
            })
            if result in ("clear","unknown"):
                break  # A clean model result or missing model NEVER causes endless retries
        except Exception as exc:
            attempts.append({"attempt":count,"status":"failed",
                             "error_type":type(exc).__name__,
                             "error":"Candidate rejected; no original file modified"})
            # Provider changes and other integrity failures are not retryable.
            if isinstance(exc,(RepairError,WaveIntegrityError)):
                break
    final=attempts[-1] if attempts else {}
    report={
        "schema_version":1,"slide":slide,"source_sha256":row["tts_source_sha256"],
        "normalized_input_sha256":row["spoken_input_sha256"],
        "original_wav_sha256":row["audio_wav_sha256"],
        "attempts":attempts,"attempt_count":len(attempts),
        "bounded":True,
        "technical_candidate_ready":final.get("acoustic_assessment")=="clear",
        "human_listening_approved":False,
        "publishable":False,
        "promotion_allowed":False,
        "status":("CANDIDATE_REVIEW_REQUIRED" if final.get("acoustic_assessment")=="clear"
                  else "ACOUSTIC_QA_UNAVAILABLE" if final.get("acoustic_assessment")=="unknown"
                  else "REPAIR_UNRESOLVED"),
    }
    receipt=new_stage/"repair_receipt.json"
    if receipt.exists(): raise RepairError("Unexpected existing receipt")
    receipt.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
    return report
