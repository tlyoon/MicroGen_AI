"""Conservative audio-recognition-to-PDF highlight candidate, not final sync QA.

Only unique, high-confidence content words match; all mathematical letters,
equations, repeated terms and unsupported geometry remain unhighlighted.
A Vosk timestamp is a real ASR-derived observation, not independently
authenticated actual spoken-word timing or conceptual slide-element intent.
"""
from __future__ import annotations
import collections
import json
import math
import re
import shutil
import subprocess
import wave
from pathlib import Path

import pymupdf as fitz

from microgen_quality import check_video
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,OrchestratorError
from microgen_offline_pronunciation_contrast import _validated_transcripts

class HighlightPilotError(OrchestratorError):
    pass

_BLOCKED={
    "about","after","again","along","also","another","around","because",
    "before","could","every","first","function","functions","given","have",
    "just","like","make","means","more","must","only","other","point",
    "should","since","some","than","that","their","these","they","this",
    "three","through","times","under","using","value","values","were",
    "when","where","which","while","would","your","youre",
}

def _word(value):
    name=re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$","",str(value)).lower()
    return name if re.fullmatch(r"[a-z]{5,24}",name) else ""

def _wav_duration(path):
    with wave.open(str(path),"rb") as audio:
        if (audio.getnchannels()!=1 or audio.getsampwidth()!=2 or
            not 8000<=audio.getframerate()<=48000):
            raise HighlightPilotError("Candidate mono PCM16 WAV required")
        duration=audio.getnframes()/audio.getframerate()
    if not .1<duration<600:
        raise HighlightPilotError("Candidate WAV duration unsafe")
    return duration

def propose_unique_word_cues(review_dir,asr_report,slide_pdf,slide,risk_class,
                             *,minimum_confidence=.9,max_cues=16):
    if type(slide) is not int or not 1<=slide<=500:
        raise HighlightPilotError("Invalid PDF slide index")
    if (not isinstance(risk_class,str) or
        not .5<=minimum_confidence<=1 or
        type(max_cues) is not int or not 1<=max_cues<=64):
        raise HighlightPilotError("Invalid conservative cue policy")
    root=Path(review_dir).resolve(strict=True)
    manifest,asr=_validated_transcripts(root,read_json(asr_report))
    pdf=Path(slide_pdf).resolve(strict=True)
    if pdf.is_symlink() or not pdf.is_file() or digest(pdf)!=manifest["source_slide_pdf_sha256"]:
        raise HighlightPilotError("Source PDF checksum differs from review bundle")
    matches=[c for c in manifest["historical_audio_candidates"]
             if c["slide"]==slide and c["risk_class"]==risk_class]
    if len(matches)!=1:
        raise HighlightPilotError("Unknown or ambiguous corrected audio candidate")
    trial=matches[0]
    audio=root/"unapproved_trials"/f"slide{slide:02d}_{risk_class}_UNREVIEWED.wav"
    duration=_wav_duration(audio)
    if digest(audio)!=trial["wav_sha256"]:
        raise HighlightPilotError("Source-bound corrective trial has changed")
    word_report=asr[audio.name]
    spoken=word_report["words"]
    speech_count=collections.Counter(_word(x["word"]) for x in spoken)
    with fitz.open(pdf) as doc:
        if slide>doc.page_count:
            raise HighlightPilotError("Slide index outside source PDF")
        page=doc[slide-1]
        words=page.get_text("words")
        pdf_count=collections.Counter(_word(w[4]) for w in words)
        geometry={_word(w[4]):list(map(float,w[:4])) for w in words
                  if _word(w[4])}
    candidates=[]
    for item in spoken:
        term=_word(item["word"])
        if (not term or term in _BLOCKED or speech_count[term]!=1 or
            pdf_count[term]!=1 or item["conf"]<minimum_confidence):
            continue
        begin,end=float(item["start"]),float(item["end"])
        if not 0<=begin<end<=duration+.025 or end-begin<.09:
            continue
        box=geometry[term]
        if any(not math.isfinite(x) for x in box):
            raise HighlightPilotError("Non-finite PDF coordinates")
        candidates.append({"text":term,"box":box,
             "start_seconds":round(begin,5),"end_seconds":round(min(end,duration),5),
             "confidence":item["conf"],
             "source_word_unique_in_pdf":True,
             "audio_word_unique_in_asr":True,
             "mathematical_semantic_match_reviewed":False})
    candidates.sort(key=lambda c:c["start_seconds"])
    if not candidates:
        raise HighlightPilotError("No unambiguous source/PDF word matches")
    candidates=candidates[:max_cues]
    return {"slide":slide,"risk_class":risk_class,
        "source_pdf_sha256":digest(pdf),
        "candidate_wav_sha256":digest(audio),
        "asr_report_sha256":digest(asr_report),
        "wav_duration_seconds":round(duration,6),
        "cues":candidates,
        "candidate_only":True,
        "math_equation_alignment_verified":False,
        "spoken_word_identity_verified":False,
        "publication_allowed":False}

def render_source_bound_highlight(review_dir,asr_report,slide_pdf,slide,
                                   risk_class,destination,*,ffmpeg):
    from microgen_production_bridge import render_staged_highlight
    root=Path(review_dir).resolve(strict=True)
    pdf=Path(slide_pdf).resolve(strict=True)
    dest=Path(destination).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest==root or
        dest.is_relative_to(root) or root.is_relative_to(dest) or
        dest==pdf.parent or dest.is_relative_to(pdf.parent)):
        raise HighlightPilotError("Candidate stage must be new and independent")
    proposal=propose_unique_word_cues(root,asr_report,pdf,slide,risk_class)
    audio=root/"unapproved_trials"/f"slide{slide:02d}_{risk_class}_UNREVIEWED.wav"
    ff=Path(ffmpeg)
    if not ff.is_file():
        raise HighlightPilotError("FFmpeg executable required")
    dest.mkdir(parents=True)
    (dest/"inputs").mkdir()
    (dest/"media").mkdir()
    page_pdf=dest/"inputs"/"source_single_slide.pdf"
    with fitz.open(pdf) as full:
        with fitz.open() as one:
            one.insert_pdf(full,from_page=slide-1,to_page=slide-1)
            one.save(page_pdf)
    target=dest/"media"/f"slide{slide:02d}_{risk_class}_ASR_TIMED_NOT_PUBLISHED.mp4"
    render_staged_highlight(page_pdf,audio,proposal["cues"],target,ffmpeg_exe=str(ff))
    check=check_video(target)
    if not 0<check["seconds"]<600 or abs(check["seconds"]-proposal["wav_duration_seconds"])>1:
        raise HighlightPilotError("Video length or A/V correspondence invalid")
    if digest(pdf)!=proposal["source_pdf_sha256"] or digest(audio)!=proposal["candidate_wav_sha256"]:
        raise HighlightPilotError("PDF or WAV changed during rendering")
    result={**proposal,"video_sha256":digest(target),"video_seconds":check["seconds"],
       "technical_asr_timed_overlay_rendered":True,
       "actual_word_to_mathematical_element_sync_certified":False,
       "published":False}
    atomic_json(dest/"candidate_receipt.json",result)
    return {"status":"TECHNICAL_ASR_WORD_HIGHLIGHT_CANDIDATE",
       "video":str(target),"video_seconds":check["seconds"],
       "cue_count":len(proposal["cues"]),
       "actual_word_to_math_sync_verified":False,"publication_allowed":False}
