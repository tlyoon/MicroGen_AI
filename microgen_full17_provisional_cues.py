"""Source-SHA-bound full 17-slide offline ASR word-cue inventory.

A cue here is an uncertain ASR observation matched to one PDF word, *not*
independently established spoken word, equation or mathematical figure intent.
No TTS provider, network/model download, source mutation or publication.
"""
from __future__ import annotations
import collections
import json
import math
from pathlib import Path

import pymupdf as fitz
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,verify_workspace,OrchestratorError
from microgen_offline_vosk_capture import validate_vosk_words
from microgen_offline_asr_pdf_highlight import _word,_BLOCKED

class WholeLectureError(OrchestratorError):
    pass

def prepare_full17_cues(legacy_workspace,asr_report,output,*,minimum_confidence=.90):
    root=Path(legacy_workspace).resolve(strict=True)
    receipt=verify_workspace(root)
    source=Path(receipt["source_root"]).resolve(strict=True)
    out=Path(output).resolve(strict=False)
    if out.exists() or out.is_symlink() or (out==source or out.is_relative_to(source) or
         out==root or out.is_relative_to(root)):
        raise WholeLectureError("Refuse to write inside source, recovery or an existing report")
    if (receipt["slide_count"]!=17 or
       not isinstance(minimum_confidence,(float,int)) or
       not .75<=minimum_confidence<=1):
        raise WholeLectureError("Bounded slide count and high confidence required")
    original=read_json(root/"legacy_mp4_audio_receipt.json")
    if (original.get("status")!="PROVISIONAL_NOT_PUBLISHABLE" or
        original["scene_evidence"].get("mp4_sha256")!=digest(source/"slides.mp4")):
        raise WholeLectureError("Untrusted legacy source evidence")
    asr=read_json(asr_report)
    if (asr.get("status")!="SOURCE_BOUND_OFFLINE_17_SLIDE_ASR" or
        asr.get("source_pdf_sha256")!=receipt["source_pdf_sha256"] or
        asr.get("narration_sha256")!=receipt["narration_sha256"] or
        asr.get("source_mp4_sha256")!=original["scene_evidence"]["mp4_sha256"] or
        asr.get("publication_allowed") is not False):
        raise WholeLectureError("ASR output is not bound to exact source")
    items=asr.get("results")
    if (not isinstance(items,list) or len(items)!=17 or
        [row.get("slide") for row in items]!=list(range(1,18))):
        raise WholeLectureError("Missing or duplicated offline slide ASR result")
    manifest=[]
    with fitz.open(source/"slides.pdf") as pdf:
        if pdf.page_count!=17:raise WholeLectureError("PDF source changed")
        for index,item in enumerate(items,1):
            audio=root/"audio"/f"slide{index}.wav"
            record=original["clips"][index-1]
            if (record.get("slide")!=index or audio.is_symlink() or not audio.is_file() or
                digest(audio)!=item.get("source_wav_sha256") or
                digest(audio)!=record.get("sha256")):
                raise WholeLectureError("Slide audio is not the original recovered source")
            duration=float(record["duration_seconds"])
            words=validate_vosk_words(item.get("words"),limit_seconds=duration+.04)
            counts=collections.Counter(_word(w["word"]) for w in words)
            pdfwords=pdf[index-1].get_text("words")
            pdfcount=collections.Counter(_word(w[4]) for w in pdfwords)
            geometry={_word(w[4]):list(map(float,w[:4])) for w in pdfwords if _word(w[4])}
            cues=[]
            for obs in words:
                token=_word(obs["word"])
                if (not token or token in _BLOCKED or obs["conf"]<minimum_confidence
                    or counts[token]!=1 or pdfcount[token]!=1 or
                    obs["end"]-obs["start"]<.09 or
                    not 0<=obs["start"]<obs["end"]<=duration+.02):
                    continue
                box=geometry[token]
                if not all(math.isfinite(v) for v in box):
                    raise WholeLectureError("Invalid PDF geometry")
                cues.append({"text":token,"box":box,
                    "start_seconds":obs["start"],"end_seconds":min(obs["end"],duration),
                    "model_confidence":obs["conf"]})
            if len(cues)>64:raise WholeLectureError("Unbounded per-slide highlight suggestions")
            manifest.append({"slide":index,"audio_sha256":digest(audio),
                "duration_seconds":duration,
                "recognized_words":len(words),"cues":cues,
                "math_semantics_verified":False})
    if digest(source/"slides.pdf")!=receipt["source_pdf_sha256"]:
        raise WholeLectureError("Original PDF mutated during extraction")
    report={"schema_version":1,
        "status":"FULL17_PROVISIONAL_AUDIO_TO_PDF_WORD_CUES",
        "slide_count":17,"source_root":str(source),
        "original_slide_pdf_sha256":receipt["source_pdf_sha256"],
        "narration_sha256":receipt["narration_sha256"],
        "source_mp4_sha256":original["scene_evidence"]["mp4_sha256"],
        "asr_report_sha256":digest(asr_report),
        "original_workspace":str(root),
        "slides":manifest,
        "total_recognized_words":sum(row["recognized_words"] for row in manifest),
        "total_cues":sum(len(row["cues"]) for row in manifest),
        "source_audio_is_legacy_scene_partition":True,
        "independent_word_alignment_verified":False,
        "mathematical_figure_alignment_verified":False,
        "pronunciation_verified":False,"publication_allowed":False,
        "source_modified":False}
    atomic_json(out,report)
    return {"report":str(out),"slides":len(manifest),
        "recognized_words":report["total_recognized_words"],"cues":report["total_cues"],
        "publication_allowed":False}
