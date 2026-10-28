"""Offline word-to-PDF *candidate* cues for CURRENT HP textbook-to-TTS run.

Source/WAV/model hash-bound; resumable after each slide. ASR is not a phonetic,
mathematical, diagram, speaker or publication certificate. No source mutation.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import re
import wave
from pathlib import Path

import pymupdf

from microgen_offline_vosk_capture import capture_offline_words, validate_vosk_words
from microgen_source_safe_orchestrator import atomic_json, digest, read_json


class FreshCueError(ValueError):
    pass


def token(value):
    return re.sub(r"[^a-z0-9]","",str(value).lower())


def source_inventory(stage):
    base=Path(stage).resolve(strict=True)
    pdf=base/"slides.pdf"
    if pdf.is_symlink() or not pdf.is_file():raise FreshCueError("No regular slides PDF")
    with pymupdf.open(pdf) as book:total=len(book)
    if total<2 or total>200:raise FreshCueError("Unsafe slide count")
    slides=[]
    for i in range(1,total+1):
        path=base/f"slide{i}.wav"
        if path.is_symlink() or not path.is_file():raise FreshCueError("Missing regular WAV")
        with wave.open(str(path),"rb") as w:
            dur=w.getnframes()/w.getframerate()
            if (w.getnchannels()!=1 or w.getsampwidth()!=2 or
                    w.getframerate() not in (16000,24000,48000) or
                    not .1<dur<=75):
                raise FreshCueError("Invalid current WAV format/duration")
        slides.append({"slide":i,"wav_sha256":digest(path),
                       "duration_seconds":round(dur,6)})
    return base,{"slides_pdf_sha256":digest(pdf),
                 "wav_inventory":slides,"slide_count":total}


def _cue_candidates(pdf_page,observation,seconds,*,confidence=.90):
    obs=validate_vosk_words(observation,limit_seconds=seconds)
    voice=collections.Counter(token(w["word"]) for w in obs)
    pdfwords=pdf_page.get_text("words")
    paper=collections.Counter(token(w[4]) for w in pdfwords)
    positions={token(w[4]):list(map(float,w[:4])) for w in pdfwords if token(w[4])}
    cues=[]
    for w in obs:
        t=token(w["word"])
        if (len(t)<4 or voice[t]!=1 or paper[t]!=1 or
                float(w["conf"])<confidence or
                float(w["end"])-float(w["start"])<.09):
            continue
        cues.append({"text":t,"start":round(float(w["start"]),5),
                     "end":round(float(w["end"]),5),
                     "box":positions[t],"confidence":float(w["conf"])})
    return cues


def generate_fresh_cues(stage,model_dir,ffmpeg,output,*,batch=23):
    base,source=source_inventory(stage)
    model=Path(model_dir).resolve(strict=True)
    ff=Path(ffmpeg).resolve(strict=True)
    if (not (model/"am").is_dir() or not ff.is_file() or
            model.is_symlink() or ff.is_symlink()):
        raise FreshCueError("Installed offline model/FFmpeg required")
    target=Path(output).absolute()
    if (target.is_symlink() or target==base or target.is_relative_to(base)
            or base.is_relative_to(target) or target.is_relative_to(model)):
        raise FreshCueError("Output must be a separate review directory")
    if not 1<=batch<=source["slide_count"]:raise FreshCueError("Invalid batch")
    model_id=hashlib.sha256(str(model).encode()).hexdigest()
    session={"schema_version":1,"status":"CURRENT_TTS_ASR_CUE_CHECKPOINT_NOT_APPROVED",
             "source":source,"model_dir":str(model),"model_identity_sha256":model_id,
             "publication_allowed":False}
    if target.exists():
        if not target.is_dir() or read_json(target/"session.json")!=session:
            raise FreshCueError("Changed source/model for existing checkpoint")
    else:
        target.mkdir(parents=True,exist_ok=False)
        atomic_json(target/"session.json",session)
    allowed={"session.json","current_tts_cues.json"}|{
        f"slide{i:02d}.json" for i in range(1,source["slide_count"]+1)}
    if any(x.is_symlink() or x.name not in allowed for x in target.iterdir()):
        raise FreshCueError("Unexpected file or symlink in checkpoint")
    if (target/"current_tts_cues.json").exists():
        raise FreshCueError("Finished report is immutable")
    todo=[i for i in range(1,source["slide_count"]+1)
          if not (target/f"slide{i:02d}.json").exists()]
    if todo:
        from vosk import Model
        recognizer=Model(str(model))
        for i in todo[:batch]:
            wav=base/f"slide{i}.wav"
            obs=capture_offline_words(wav,recognizer,ff)
            if obs["source_wav_sha256"]!=source["wav_inventory"][i-1]["wav_sha256"]:
                raise FreshCueError("WAV mutated during inference")
            with pymupdf.open(base/"slides.pdf") as book:
                cues=_cue_candidates(book[i-1],obs["words"],
                       source["wav_inventory"][i-1]["duration_seconds"])
            row={"slide":i,"wav_sha256":obs["source_wav_sha256"],
                 "observed_words":len(obs["words"]),"cues":cues,
                 "recognition":obs,"publication_allowed":False}
            if source_inventory(base)[1]!=source:
                raise FreshCueError("Source mutation during recognition")
            atomic_json(target/f"slide{i:02d}.json",row)
            print("ASR_SLIDE",i,"WORDS",len(obs["words"]),"UNIQUE_CUES",len(cues),flush=True)
    final=[]
    for i in range(1,source["slide_count"]+1):
        path=target/f"slide{i:02d}.json"
        if not path.exists():continue
        row=read_json(path)
        expected=source["wav_inventory"][i-1]
        if (row.get("slide")!=i or row.get("wav_sha256")!=expected["wav_sha256"] or
            row.get("publication_allowed") is not False or
            row.get("recognition",{}).get("source_wav_sha256")!=expected["wav_sha256"]):
            raise FreshCueError("Invalid resumed slide observation")
        words=validate_vosk_words(row["recognition"]["words"],
                                  limit_seconds=expected["duration_seconds"])
        with pymupdf.open(base/"slides.pdf") as book:
            actual=_cue_candidates(book[i-1],words,expected["duration_seconds"])
        if actual!=row["cues"]:raise FreshCueError("Unbound/forged word cues")
        final.append(row)
    if source_inventory(base)[1]!=source:
        raise FreshCueError("Source changed after inference")
    if len(final)==source["slide_count"]:
        receipt={"schema_version":1,"status":"CURRENT_23_SLIDE_ASR_CANDIDATES_NOT_ACADEMIC_APPROVAL",
                 "source":source,"recognition_model_sha256":model_id,
                 "total_cues":sum(len(x["cues"]) for x in final),
                 "slides":[{"slide":x["slide"],"wav_sha256":x["wav_sha256"],
                            "observed_words":x["observed_words"],"cues":x["cues"]}
                           for x in final],
                 "phonetic_correctness_verified":False,
                 "figure_equation_alignment_verified":False,
                 "publication_allowed":False}
        atomic_json(target/"current_tts_cues.json",receipt)
    return {"processed":len(final),"total":source["slide_count"],
            "candidate_cues":sum(len(x["cues"]) for x in final),
            "publication_allowed":False,
            "complete":len(final)==source["slide_count"]}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--ffmpeg",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--batch",type=int,default=23)
    a=p.parse_args()
    print(json.dumps(generate_fresh_cues(a.stage,a.model,a.ffmpeg,
                                         a.output,batch=a.batch)))
