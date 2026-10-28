"""Offline ASR pronunciation contrast diagnostic, never publication approval.

Supports Vosk speech-to-text data if present locally. Neither the model
transcript nor its word timestamps are authenticated spoken phonemes or
a guarantee of semantic equation-to-narration alignment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from microgen_source_safe_orchestrator import read_json, digest, atomic_json, OrchestratorError

class ASRContrastError(OrchestratorError):
    pass

def _candidate_filename(row):
    return f"slide{row['slide']:02d}_{row['risk_class']}_UNREVIEWED.wav"

def _validated_transcripts(review_dir,asr):
    root=Path(review_dir).resolve(strict=True)
    manifest=read_json(root/"review_manifest.json")
    if (manifest.get("status")!="TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED"
       or manifest.get("publication_allowed") is not False):
        raise ASRContrastError("Source candidate review manifest missing or unsupported")
    if asr.get("publication_allowed") is not False or asr.get("model_word_timestamps_not_ground_truth") is not True:
        raise ASRContrastError("ASR output must explicitly abstain from publication")
    if not isinstance(asr.get("model"),str) or not asr["model"]:
        raise ASRContrastError("ASR model not identified")
    candidates=manifest.get("historical_audio_candidates")
    if not isinstance(candidates,list) or not candidates:
        raise ASRContrastError("Historical QA trials missing")
    required={}
    for slide in manifest["slides_to_review"]:
        if type(slide) is not int or not 1<=slide<=500:
            raise ASRContrastError("Invalid slide index")
        name=f"slide{slide:02d}_reference.wav"
        p=root/"original_scene_references"/name
        if not p.is_file() or p.is_symlink():
            raise ASRContrastError("Source reference WAV missing")
        required[name]=digest(p)
    for row in candidates:
        if (not isinstance(row,dict) or row.get("publication_allowed") is not False
            or row.get("phonetic_approved") is not False):
            raise ASRContrastError("Candidate improperly approved")
        name=_candidate_filename(row)
        p=root/"unapproved_trials"/name
        if p.is_symlink() or not p.is_file() or digest(p)!=row["wav_sha256"]:
            raise ASRContrastError("Trial recording hash mismatch")
        if name in required:
            raise ASRContrastError("Duplicate recording identity")
        required[name]=row["wav_sha256"]
    results=asr.get("results")
    if not isinstance(results,list) or len(results)!=len(required):
        raise ASRContrastError("Incomplete ASR recordings")
    by_name={}
    for row in results:
        if not isinstance(row,dict) or row.get("file") in by_name:
            raise ASRContrastError("Duplicate or invalid ASR file")
        name=row["file"]
        if name not in required or row.get("source_wav_sha256")!=required[name]:
            raise ASRContrastError("ASR transcript not bound to actual WAV")
        if row.get("phonetic_identity_verified") is not False or row.get("semantic_word_alignment_certified") is not False:
            raise ASRContrastError("Unauthenticated ASR confidence escalation")
        words=row.get("words")
        if not isinstance(words,list) or len(words)>1000:
            raise ASRContrastError("Invalid ASR word collection")
        last=0.
        for word in words:
            if not isinstance(word,dict) or not isinstance(word.get("word"),str):
                raise ASRContrastError("Invalid ASR word")
            t0,t1,conf=word.get("start"),word.get("end"),word.get("conf")
            if (any(type(v) not in (float,int) or not math.isfinite(v)
                     for v in (t0,t1,conf))
                    or not 0<=t0<=t1<=75 or not 0<=conf<=1 or t0<last):
                raise ASRContrastError("ASR word clock not monotone or confidence invalid")
            last=t0
        by_name[name]=row
    return manifest,by_name

def _count(words,tokens):
    return sum(1 for word in words if word["word"].lower() in tokens)

def _events(words,tokens):
    return [{"word":w["word"],"time_seconds":w["start"],
             "confidence":w["conf"]} for w in words
            if w["word"].lower() in tokens]

def assess_pronunciation_contrast(review_dir,asr_report):
    root=Path(review_dir).resolve(strict=True)
    doc=read_json(asr_report)
    manifest,rec=_validated_transcripts(root,doc)
    rows=[]
    for trial in manifest["historical_audio_candidates"]:
        i=trial["slide"]
        reference=rec[f"slide{i:02d}_reference.wav"]
        candidate=rec[_candidate_filename(trial)]
        old=reference["words"];new=candidate["words"]
        risk=trial["risk_class"]
        if risk=="CDOT":
            suspected={"circa"}
            intended={"see","sea"}
        elif risk in ("Y_VALUE","Y_VALUE_ALT"):
            suspected={"yay"}
            intended={"why"}
        else:
            raise ASRContrastError("Unknown risk class")
        suspect_old=_events(old,suspected)
        suspect_new=_events(new,suspected)
        desired_old=_events(old,intended)
        desired_new=_events(new,intended)
        credible_old=[w for w in suspect_old if w["confidence"]>=0.75]
        credible_new=[w for w in desired_new if w["confidence"]>=0.70]
        if (risk=="CDOT" and credible_old and not suspect_new and credible_new):
            assessment="AUTOMATED_CONTRAST_SUGGESTS_CIRCA_REDUCED"
        elif (risk.startswith("Y_VALUE") and not suspect_new and
              len(credible_new)>len([w for w in desired_old if w["confidence"]>=0.70])):
            assessment="ASR_SUGGESTS_ADDITIONAL_Y_LETTER_NAME"
        else:
            assessment="ASR_INCONCLUSIVE_OR_NO_IMPROVEMENT"
        rows.append({
            "slide":i,"risk_class":risk,
            "source_media_receipt_bound":trial["source_media_receipt_bound"],
            "old_suspect_words":suspect_old,
            "new_suspect_words":suspect_new,
            "old_expected_sound_words":desired_old,
            "new_expected_sound_words":desired_new,
            "old_wav_sha256":rec[f"slide{i:02d}_reference.wav"]["source_wav_sha256"],
            "candidate_wav_sha256":trial["wav_sha256"],
            "assessment":assessment,
            "model_confidence_not_phonetic_truth":True,
            "listening_and_voice_review_required":True,
            "eligible_for_replacement":False})
    return {"schema_version":1,
        "status":"OFFLINE_ASR_CONTRAST_REVIEW_REQUIRED",
        "model":doc["model"],"model_download_sha256":doc.get("model_download_sha256"),
        "original_source_mp4_sha256":manifest["source_mp4_sha256"],
        "narration_sha256":manifest["narration_sha256"],
        "candidate_assessments":rows,
        "independent_speech_ground_truth_verified":False,
        "spoken_word_to_visual_element_sync_verified":False,
        "phonetic_accuracy_verified":False,
        "voice_identity_verified":False,
        "human_listening_review_done":False,
        "publication_allowed":False,
        "source_modified":False}

def main(argv=None):
    parser=argparse.ArgumentParser(description="Offline pronunciation transcript SHA contrast (QA only)")
    parser.add_argument("--review-dir",type=Path,required=True)
    parser.add_argument("--asr-report",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        raise ASRContrastError("Refusing existing output")
    result=assess_pronunciation_contrast(args.review_dir,args.asr_report)
    atomic_json(args.output,result)
    print(json.dumps({"status":result["status"],
        "evaluated":len(result["candidate_assessments"]),
        "publication_allowed":False,"output":str(args.output)}))
    return 2

if __name__=="__main__":
    raise SystemExit(main())
