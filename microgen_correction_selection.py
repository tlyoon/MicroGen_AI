"""Select provenance-verified historical pronunciation trials for *shadow* QA.

This selector does not claim the provider voice identity or auditory correctness.
Only an explicit unique trial per known slide can be staged separately.
"""
from pathlib import Path
import shutil
from microgen_source_safe_orchestrator import verify_workspace,digest,read_json,atomic_json,OrchestratorError

class TrialSelectionError(OrchestratorError):
    pass

def select_source_bound_trials(recovery,review_directory,destination):
    old=Path(recovery).resolve(strict=True)
    review=Path(review_directory).resolve(strict=True)
    source=verify_workspace(old)
    metadata=read_json(review/"review_manifest.json")
    output=Path(destination).resolve(strict=False)
    if (output.exists() or output.is_symlink() or output.is_relative_to(old)
        or output.is_relative_to(review) or
        output.is_relative_to(Path(source["source_root"]).resolve(strict=True))):
        raise TrialSelectionError("Refuse overwrite or protected folders")
    if (metadata.get("status")!="TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED"
        or metadata.get("publication_allowed") is not False or
        metadata.get("source_mp4_sha256")!=digest(Path(source["source_root"])/"slides.mp4")
        or metadata.get("source_slide_pdf_sha256")!=source["source_pdf_sha256"]
        or metadata.get("narration_sha256")!=source["narration_sha256"]):
        raise TrialSelectionError("QA manifest not bound to the unchanged original")
    expected={5:"CDOT",6:"CDOT",10:"Y_VALUE"}
    rows=metadata.get("historical_audio_candidates",[])
    selected=[]
    for slide,risk in expected.items():
        matching=[r for r in rows if r.get("slide")==slide and r.get("risk_class")==risk
                  and r.get("source_media_receipt_bound") is True]
        if len(matching)!=1:
            raise TrialSelectionError("No uniquely source-bound corrected trial")
        row=matching[0]
        original=review/"unapproved_trials"/f"slide{slide:02d}_{risk}_UNREVIEWED.wav"
        if (original.is_symlink() or not original.is_file() or
            digest(original)!=row["wav_sha256"] or
            row.get("phonetic_approved") is not False):
            raise TrialSelectionError("Unapproved trial's SHA or status differs")
        selected.append((slide,risk,original,row["wav_sha256"]))
    output.mkdir(parents=True)
    report=[]
    for slide,risk,original,sha in selected:
        dst=output/f"slide{slide:02d}_{risk}_UNAPPROVED.wav"
        shutil.copyfile(original,dst)
        if digest(dst)!=sha:raise TrialSelectionError("Trial WAV changed while copied")
        report.append({"slide":slide,"risk":risk,"wav_sha256":sha,
                       "trial_path":str(dst),"voice_independently_verified":False,
                       "phonetic_approved":False})
    atomic_json(output/"selection_receipt.json",{
       "schema_version":1,"status":"SHADOW_ONLY_TRIAL_SELECTION",
       "source_pdf_sha256":source["source_pdf_sha256"],
       "source_narration_sha256":source["narration_sha256"],
       "source_mp4_sha256":metadata["source_mp4_sha256"],
       "trials":report,"publication_allowed":False,
       "original_audio_modified":False})
    return {"trials":len(report),"slides":[r["slide"] for r in report],
            "directory":str(output),"publication_allowed":False}
