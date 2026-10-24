"""Source-bound offline pronunciation risk timestamps, not phonetic proof."""
from __future__ import annotations
from pathlib import Path
import json
from microgen_source_safe_orchestrator import verify_workspace,digest,read_json,atomic_json,OrchestratorError
from microgen_offline_vosk_capture import validate_vosk_words

class DefectEvidenceError(OrchestratorError):
    pass

def map_legacy_pronunciation_defects(workspace,asr_json,output,*,minimum_confidence=.75):
    root=Path(workspace).resolve(strict=True)
    receipt=verify_workspace(root)
    report=read_json(asr_json)
    dest=Path(output).resolve(strict=False)
    source=Path(receipt["source_root"]).resolve(strict=True)
    if (dest.exists() or dest.is_symlink() or dest.is_relative_to(root)
        or dest.is_relative_to(source)):
        raise DefectEvidenceError("Evidence report must be new and outside source")
    if not .5<=minimum_confidence<=1:
        raise DefectEvidenceError("Invalid confidence threshold")
    recovered=read_json(root/"legacy_mp4_audio_receipt.json")
    if (report.get("status")!="SOURCE_BOUND_OFFLINE_17_SLIDE_ASR" or
        report.get("publication_allowed") is not False or
        report.get("source_pdf_sha256")!=receipt["source_pdf_sha256"] or
        report.get("narration_sha256")!=receipt["narration_sha256"] or
        report.get("source_mp4_sha256")!=digest(source/"slides.mp4")):
        raise DefectEvidenceError("ASR source binding invalid")
    rows=report.get("results")
    if not isinstance(rows,list) or len(rows)!=17 or [r.get("slide") for r in rows]!=list(range(1,18)):
        raise DefectEvidenceError("Requires exactly 17 real slide results")
    risks=[]
    intervals=[];elapsed=0.
    for i,row in enumerate(rows,1):
        wav=root/"audio"/f"slide{i}.wav"
        src=recovered["clips"][i-1]
        if (src["slide"]!=i or digest(wav)!=row.get("source_wav_sha256")
            or digest(wav)!=src["sha256"]):
            raise DefectEvidenceError("Recovered original WAV changed")
        duration=float(src["duration_seconds"])
        words=validate_vosk_words(row.get("words"),limit_seconds=duration+.05)
        for word in words:
            token=word["word"].lower()
            if token not in {"circa","yay","why","see","sea"}:
                continue
            if word["conf"]<minimum_confidence:
                continue
            item={"slide":i,"token":token,
                "local_seconds":round(word["start"],5),
                "lecture_seconds":round(elapsed+word["start"],5),
                "model_confidence":word["conf"],
                "audio_sha256":src["sha256"],
                "requires_independent_listening":True}
            if token in ("circa","yay"):
                item["risk"]="POSSIBLE_MATH_VARIABLE_PRONUNCIATION_ERROR"
            else:
                item["risk"]="UNAUTHENTICATED_LETTER_NAME_CANDIDATE"
            risks.append(item)
        intervals.append({"slide":i,"start":round(elapsed,5),"seconds":duration})
        elapsed+=duration
    output_data={"schema_version":1,
       "status":"OFFLINE_PRONUNCIATION_RISK_TIMES_NOT_CERTIFIED",
       "source_mp4_sha256":report["source_mp4_sha256"],
       "narration_sha256":receipt["narration_sha256"],
       "asr_sha256":digest(asr_json),
       "video_original_seconds":elapsed,
       "risks":risks,"slide_timeline":intervals,
       "acoustically_authenticated":False,
       "corrected_voice_verified":False,
       "publication_allowed":False}
    atomic_json(dest,output_data)
    return {"report":str(dest),"risk_observations":len(risks),
        "circa_sightings":sum(x["token"]=="circa" for x in risks),
        "publication_allowed":False}
