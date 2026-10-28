"""Non-destructive, SHA-anchored real textbook TTS repair pilot.

This module *prepares* and exercises isolated candidate WAV/video input.
Only a separate, already-configured renderer creates a review MP4.
It cannot publish, upload or replace any historical teaching asset.
"""
from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

from microgen_tts_repair import stage_repair, RepairError
from microgen_tts_risk_register import (
    build_risk_register,durations_from_wavs,
)
from microgen_tts_provenance import digest_file,wav_characteristics

class PilotError(RuntimeError):
    pass

def file_digest(file:Path)->str:
    return digest_file(file)

def _contained_or_equal(parent:Path,child:Path)->bool:
    a=parent.resolve();b=child.resolve()
    return a==b or a in b.parents

def prepare_pilot(
    original_qa:Path, historical_bad_wav:Path, root:Path, *,
    slide:int, historical_bad_sha256:str,
    good_reference_sha256:str, normalize:Callable[[str],str],
) -> dict:
    """Copy verified 17-slide QA input and inject old defective WAV *only in scratch*."""
    original_qa=Path(original_qa);historical_bad_wav=Path(historical_bad_wav)
    root=Path(root)
    if root.exists() or root.is_symlink():
        raise PilotError("Refusing existing pilot root")
    if _contained_or_equal(original_qa,root):
        raise PilotError("Pilot output must not be under input lecture directory")
    if not historical_bad_wav.is_file() or file_digest(historical_bad_wav)!=historical_bad_sha256:
        raise PilotError("Historical defective WAV checksum mismatch")
    if not historical_bad_wav.is_relative_to(original_qa):
        raise PilotError("Historical WAV must be a source-side reviewed backup")
    sidecar=original_qa/"script_tts.json"
    pdf=original_qa/"slides.pdf"
    if not sidecar.is_file() or not pdf.is_file():
        raise PilotError("Source slides and TTS script missing")
    slides=json.loads(sidecar.read_text(encoding="utf8")).get("slides",[])
    if not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise PilotError("Unexpected slide ordering")
    if not (isinstance(slide,int) and 1<=slide<=len(slides)):
        raise PilotError("Bad repair slide")
    input_wavs=[original_qa/f"slide{i}.wav" for i in range(1,len(slides)+1)]
    if not all(x.is_file() for x in input_wavs):
        raise PilotError("Incomplete source WAV set")
    for wav in input_wavs:
        wav_characteristics(wav)
    if file_digest(input_wavs[slide-1])!=good_reference_sha256:
        raise PilotError("Previously human-reviewed corrected WAV checksum changed")
    stage=root/"pre_repair"
    root.mkdir(parents=True)
    stage.mkdir()
    shutil.copy2(sidecar,stage/"script_tts.json")
    shutil.copy2(pdf,stage/"slides.pdf")
    for count,wav in enumerate(input_wavs,1):
        shutil.copy2(historical_bad_wav if count==slide else wav,stage/f"slide{count}.wav")
    count=len(slides)
    durations=durations_from_wavs(stage,count)
    wav_hashes=[file_digest(stage/f"slide{i}.wav") for i in range(1,count+1)]
    register=build_risk_register(slides,normalize,durations,wav_sha256=wav_hashes)
    if slide not in register["suggested_isolated_repair_slides"]:
        raise PilotError("Historical repair slide is not covered by a reviewed rule")
    (root/"risk_register.json").write_text(
        json.dumps(register,indent=2,ensure_ascii=False),encoding="utf8")
    metadata={
       "schema_version":1,"slide":slide,
       "original_qa":str(original_qa),"scratch_root":str(root),
       "historical_bad_wav_sha256":historical_bad_sha256,
       "human_listening_confirmed_reference_sha256":good_reference_sha256,
       "pre_repair_wav_sha256":wav_hashes,
       "original_script_sha256":file_digest(sidecar),
       "original_slide_pdf_sha256":file_digest(pdf),
       "production_media_touched":False,
       "review_stage_only":True,
       "publishable":False,
    }
    (root/"pilot_source_receipt.json").write_text(
        json.dumps(metadata,indent=2),encoding="utf8")
    return metadata

def repair_and_prepare_video_stage(
    root:Path, *, normalize:Callable[[str],str],
    synthesize:Callable[[str,Path],str], slide:int,
    pinned_provider:str="google_cloud_chirp3",
    pinned_voice:str="en-US-Chirp-HD-F", pinned_rate:float=0.8,
    max_attempts:int=1,
) -> dict:
    """Stage-only real TTS call with no acoustic model claims or publisher actions."""
    root=Path(root)
    source_receipt=json.loads((root/"pilot_source_receipt.json").read_text(encoding="utf8"))
    if slide!=source_receipt.get("slide"):
        raise PilotError("Pilot slide identity drift")
    stage=root/"pre_repair"
    register=json.loads((root/"risk_register.json").read_text(encoding="utf8"))
    for count,wav_hash in enumerate(source_receipt["pre_repair_wav_sha256"],1):
        if file_digest(stage/f"slide{count}.wav")!=wav_hash:
            raise PilotError("Pre-repair audio SHA drift")
    if file_digest(stage/"script_tts.json")!=source_receipt["original_script_sha256"]:
        raise PilotError("Pre-repair narration hash drift")
    report=stage_repair(stage,register,slide,root/"repair_candidates",
                        synthesize,normalize,provider=pinned_provider,
                        voice=pinned_voice,rate=pinned_rate,max_attempts=max_attempts)
    if report["attempt_count"]!=1 or "wav_sha256" not in report["attempts"][0]:
        return {**report,"video_stage_created":False}
    candidate=root/"repair_candidates"/report["attempts"][0]["file"]
    if file_digest(candidate)!=report["attempts"][0]["wav_sha256"]:
        raise PilotError("Candidate audio checksum drift")
    preview=root/"video_review_input"
    preview.mkdir(exist_ok=False)
    shutil.copy2(stage/"script_tts.json",preview/"script_tts.json")
    shutil.copy2(stage/"slides.pdf",preview/"slides.pdf")
    for number in range(1,len(source_receipt["pre_repair_wav_sha256"])+1):
        source=candidate if number==slide else stage/f"slide{number}.wav"
        shutil.copy2(source,preview/f"slide{number}.wav")
    duration=sum(durations_from_wavs(preview,len(source_receipt["pre_repair_wav_sha256"])))
    (preview/"README_QA_NOT_PUBLISHED.txt").write_text(
       "Unapproved repair candidate. Do not publish. Acrobat/FFmpeg review MP4 "
       "and independent acoustic and listening QA are still required.\n",
       encoding="utf8")
    final={
        "status":"REVIEW_VIDEO_INPUT_READY_NOT_PUBLISHED",
        "source":str(stage),
        "preview_stage":str(preview),"slide":slide,
        "candidate_wav_sha256":file_digest(candidate),
        "voice_requested":pinned_voice,"speaking_rate":pinned_rate,
        "provider":pinned_provider,
        "total_wav_seconds":round(duration,6),
        "requires_multipart":duration>=600,
        "acoustic_qa_passed":False,
        "human_listening_approved":False,
        "academic_qa_approved":False,
        "highlight_qa_approved":False,
        "publishable":False,
        "production_media_touched":False,
        "repair_report":report,
    }
    (root/"pilot_candidate_receipt.json").write_text(
         json.dumps(final,indent=2,ensure_ascii=False),encoding="utf8")
    return final
