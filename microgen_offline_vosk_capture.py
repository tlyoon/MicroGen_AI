"""Optional all-offline Vosk word-timestamp capture for a SHA-bound QA bundle.

No download, API call, implicit approval, Whisper, voice authentication,
maths interpretation or actual spoken-word-to-equation synchronization.
Caller installs an offline model separately; this code never fetches it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,OrchestratorError

class OfflineRecognitionError(OrchestratorError):
    pass

def validate_vosk_words(words,*,limit_seconds=75):
    if not isinstance(words,list) or len(words)>1000:
        raise OfflineRecognitionError("Unbounded recognition word list")
    prior=0.
    output=[]
    for row in words:
        if not isinstance(row,dict) or not isinstance(row.get("word"),str):
            raise OfflineRecognitionError("Missing word text")
        word=row["word"].strip().lower()
        vals=[row.get("start"),row.get("end"),row.get("conf")]
        if (not word or len(word)>100 or
            any(type(x) not in (float,int) or not math.isfinite(x) for x in vals)):
            raise OfflineRecognitionError("Invalid word text/clock")
        start,end,conf=vals
        if not prior<=start<=end<=limit_seconds+.1 or not 0<=conf<=1:
            raise OfflineRecognitionError("Unordered word times or model confidence")
        prior=start
        output.append({"word":word,"start":round(start,5),
                       "end":round(end,5),"conf":round(conf,5)})
    return output

def _decode_to_raw(wav,ffmpeg,*,max_seconds=75):
    p=Path(wav).resolve(strict=True)
    if p.is_symlink() or not p.is_file() or p.suffix.lower()!=".wav":
        raise OfflineRecognitionError("Regular WAV source required")
    if not Path(ffmpeg).is_file():
        raise OfflineRecognitionError("Explicit FFmpeg executable required")
    source_sha=digest(p)
    cmd=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error",
         "-i",str(p),"-map","0:a:0","-vn","-ac","1","-ar","16000",
         "-c:a","pcm_s16le","-f","s16le","pipe:1"]
    try:
        run=subprocess.run(cmd,capture_output=True,timeout=90)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise OfflineRecognitionError("Offline PCM decoding failed") from e
    pcm=run.stdout
    if run.returncode or not 1600<len(pcm)<=max_seconds*32000 or len(pcm)%2:
        raise OfflineRecognitionError("PCM content invalid or unbounded")
    if digest(p)!=source_sha:
        raise OfflineRecognitionError("Source WAV mutated during offline decoding")
    return pcm,source_sha

def capture_offline_words(wav,model,ffmpeg):
    """Use supplied already-installed Vosk model object, without network access."""
    try:
        from vosk import KaldiRecognizer
    except ImportError as e:
        raise OfflineRecognitionError("Optional vosk package missing") from e
    pcm,source_hash=_decode_to_raw(wav,ffmpeg)
    recognizer=KaldiRecognizer(model,16000)
    recognizer.SetWords(True)
    words=[]
    for offset in range(0,len(pcm),8192):
        if recognizer.AcceptWaveform(pcm[offset:offset+8192]):
            words.extend(json.loads(recognizer.Result()).get("result",[]))
    words.extend(json.loads(recognizer.FinalResult()).get("result",[]))
    validated=validate_vosk_words(words,limit_seconds=len(pcm)/32000)
    return {"file":Path(wav).name,"source_wav_sha256":source_hash,
      "words":validated,"phonetic_identity_verified":False,
      "semantic_word_alignment_certified":False}

def capture_review_bundle(review_dir,model_dir,ffmpeg,output,*,model_archive_sha=None):
    """Recognize every reference/trial once, still fail-closed on publication."""
    root=Path(review_dir).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    if dest.exists() or dest.is_symlink():
        raise OfflineRecognitionError("Refusing existing ASR output")
    model_path=Path(model_dir).resolve(strict=True)
    if not model_path.is_dir() or not (model_path/"am").is_dir():
        raise OfflineRecognitionError("Explicit installed Vosk acoustic model required")
    try:
        from vosk import Model
    except ImportError as e:
        raise OfflineRecognitionError("No optional offline Vosk installation") from e
    manifest=read_json(root/"review_manifest.json")
    if manifest.get("status")!="TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED":
        raise OfflineRecognitionError("Review bundle unverified")
    files=[]
    for slide in manifest["slides_to_review"]:
        p=root/"original_scene_references"/f"slide{slide:02d}_reference.wav"
        if p.is_symlink() or not p.is_file():
            raise OfflineRecognitionError("Reference recording missing")
        files.append((p,digest(p)))
    for row in manifest["historical_audio_candidates"]:
        p=root/"unapproved_trials"/f"slide{row['slide']:02d}_{row['risk_class']}_UNREVIEWED.wav"
        if p.is_symlink() or not p.is_file() or digest(p)!=row["wav_sha256"]:
            raise OfflineRecognitionError("Candidate changed since source audit")
        files.append((p,row["wav_sha256"]))
    if len(files)>24 or len({p.name for p,_ in files})!=len(files):
        raise OfflineRecognitionError("Duplicate/unbounded input inventory")
    model=Model(str(model_path))
    results=[]
    for wav,sha in files:
        observation=capture_offline_words(wav,model,ffmpeg)
        if observation["source_wav_sha256"]!=sha:
            raise OfflineRecognitionError("Original SHA changed during recognition")
        results.append(observation)
    report={"schema_version":1,"engine":"Vosk optional offline ASR",
            "model":model_path.name,"model_download_sha256":model_archive_sha,
            "results":results,"model_word_timestamps_not_ground_truth":True,
            "publication_allowed":False,"source_modified":False}
    atomic_json(dest,report)
    return {"status":"OFFLINE_ASR_DIAGNOSTIC_ONLY",
            "observations":len(results),"report":str(dest),
            "publication_allowed":False}

def main(argv=None):
    p=argparse.ArgumentParser(description="Offline Vosk QA capture; never approves speech or publication")
    p.add_argument("--review-dir",required=True,type=Path)
    p.add_argument("--model-dir",required=True,type=Path)
    p.add_argument("--ffmpeg",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--model-archive-sha")
    args=p.parse_args(argv)
    result=capture_review_bundle(args.review_dir,args.model_dir,
         args.ffmpeg,args.out,model_archive_sha=args.model_archive_sha)
    print(json.dumps(result,sort_keys=True))
    return 2

if __name__=="__main__":
    raise SystemExit(main())
