"""Source-bound §2.5 pronunciation comparison; QA only, no automatic promotion.

Reconstructing 17 slide WAVs from a legacy MP4 makes them available as
technical *reference* audio, not authenticated text-to-speech originals.
Corrected historical trial WAVs are compared under source/QA SHA evidence.
No human/ASR listening, voice identity, speech fidelity, highlight sync,
mathematical correctness or publication approval is inferred.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import wave
from pathlib import Path
from microgen_source_safe_orchestrator import (
    digest,read_json,verify_workspace,atomic_json,OrchestratorError
)

class ReviewBundleError(OrchestratorError):
    pass

_CANDIDATES=(
    (5,"QA_tts_cdot_20261019/slide5_corrected.wav","CDOT"),
    (6,"QA_tts_cdot_20261019/slide6_corrected.wav","CDOT"),
    (10,"QA_tts_y_20261019/slide10_corrected_y.wav","Y_VALUE"),
    (10,"QA_tts_PR35_20261020/slide10_PR35_unapproved.wav","Y_VALUE_ALT"),
)

def _duration(wav_path):
    with wave.open(str(wav_path),"rb") as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2:
            raise ReviewBundleError("Expected mono PCM16 only")
        sample_rate=f.getframerate()
        if not 8000<=sample_rate<=48000 or f.getnframes()<=0:
            raise ReviewBundleError("Invalid WAV sample rate or empty")
        seconds=f.getnframes()/sample_rate
        if not .05<=seconds<600:
            raise ReviewBundleError("Invalid candidate duration")
        return round(seconds,6),sample_rate

def _verify_expected_candidate(source,slide,relative_path,risk,script_sha,mp4_sha):
    """Read historical QA claims, demand matching source media and file SHA."""
    candidate=source/relative_path
    if (candidate.is_symlink() or not candidate.is_file() or
        not candidate.resolve(strict=True).is_relative_to(source)):
        raise ReviewBundleError("QA candidate missing or symlinked")
    candidate_sha=digest(candidate)
    evidence=[]
    source_bound=False
    if risk=="CDOT":
        r=read_json(source/"QA_tts_cdot_20261019"/"qa_receipt.json")
        queue=read_json(source/"QA_tts_PR39_20261020"/"all_slide_listening_queue.json")
        rows=[x for x in queue["rows"] if x["slide"]==slide]
        if (r.get("original_script_tts_sha256")!=script_sha or
            r.get("source_mp4_sha256_preserved")!=mp4_sha or
            queue.get("source_script_sha256")!=script_sha or
            len(rows)!=1 or rows[0]["wav_sha256"]!=candidate_sha or
            r.get("voice")!="en-US-Chirp-HD-F"):
            raise ReviewBundleError("C-dot trial is not bound to expected QA records")
        evidence=["source_script_sha","source_video_sha","review_queue_wav_sha"]
        source_bound=True
    elif risk=="Y_VALUE":
        r=read_json(source/"QA_tts_y_20261019"/"qa_receipt.json")
        if (r.get("original_mp4_sha256_preserved")!=mp4_sha or
            r.get("slide10_new_sha256")!=candidate_sha or
            r.get("single_configured_voice")!="en-US-Chirp-HD-F"):
            raise ReviewBundleError("Y-value QA candidate provenance mismatch")
        evidence=["source_video_sha","qa_receipt_wav_sha"]
        source_bound=True
    elif risk=="Y_VALUE_ALT":
        r=read_json(source/"QA_tts_PR35_20261020"/"repair_receipt.json")
        if (r.get("slide")!=slide or
            r.get("candidate_wav_sha256")!=candidate_sha or
            r.get("repair_report",{}).get("status")!="ACOUSTIC_QA_UNAVAILABLE"):
            raise ReviewBundleError("PR35 trial SHA or status mismatch")
        evidence=["qa_receipt_wav_sha","no_authenticated_approval"]
        # No independent source video SHA in that receipt: do not upgrade.
    else:
        raise ReviewBundleError("Unsupported explicit pronunciation risk kind")
    if r.get("publishable") is True or r.get("released") is True:
        raise ReviewBundleError("Historical review unexpectedly reports publication")
    return {"wav_sha256":candidate_sha,"evidence":evidence,
        "source_media_receipt_bound":source_bound,
        "voice_claimed":"en-US-Chirp-HD-F",
        "voice_independently_authenticated":False,
        "phonetic_approved":False}

def make_section25_review_bundle(workspace,output):
    receipt=verify_workspace(workspace)
    stage=Path(workspace).resolve(strict=True)
    source=Path(receipt["source_root"]).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest==source or
        dest==stage or dest.is_relative_to(source) or
        dest.is_relative_to(stage) or
        source.is_relative_to(dest) or stage.is_relative_to(dest)):
        raise ReviewBundleError("Output must be new and independent of source or stage")
    if (receipt["slide_count"]!=17 or
        receipt["narration_sha256"]!=digest(source/"script_tts.json")):
        raise ReviewBundleError("Not the verified 17-slide source lesson")
    proof=read_json(stage/"legacy_mp4_audio_receipt.json")
    if (proof.get("status")!="PROVISIONAL_NOT_PUBLISHABLE" or
        proof.get("scene_evidence",{}).get("mp4_sha256")!=digest(source/"slides.mp4")):
        raise ReviewBundleError("Verified legacy source MP4 recovery missing")
    if not (stage/"technical_tail_candidate_receipt.json").is_file():
        raise ReviewBundleError("Verified held-last-frame lossless candidate missing")
    tail=read_json(stage/"technical_tail_candidate_receipt.json")
    if (tail.get("status")!="TECHNICAL_END_FRAME_EXTENSION_NOT_PUBLISHABLE"
        or tail.get("original_mp4_sha256")!=digest(source/"slides.mp4")
        or tail.get("publication_allowed") is not False):
        raise ReviewBundleError("Technical original PCM receipt is not grounded")
    if not Path(tail["candidate_path"]).is_file() or digest(tail["candidate_path"])!=tail["candidate_mp4_sha256"]:
        raise ReviewBundleError("Existing technical candidate has changed")
    refs={}
    for slide,_,_ in _CANDIDATES:
        wav=stage/"audio"/f"slide{slide}.wav"
        if wav.is_symlink() or not wav.is_file():
            raise ReviewBundleError("Recovered reference WAV missing")
        rows=[x for x in proof["clips"] if x["slide"]==slide]
        if len(rows)!=1 or digest(wav)!=rows[0]["sha256"]:
            raise ReviewBundleError("Provisional source reference has changed")
        refs[slide]=wav
    candidates=[]
    for slide,relative,risk in _CANDIDATES:
        meta=_verify_expected_candidate(source,slide,relative,risk,
             receipt["narration_sha256"],digest(source/"slides.mp4"))
        p=source/relative
        seconds,rate=_duration(p)
        old_seconds,old_rate=_duration(refs[slide])
        candidates.append({**meta,
            "slide":slide,"risk_class":risk,"relative_path":relative,
            "candidate_duration_seconds":seconds,"reference_duration_seconds":old_seconds,
            "duration_change_seconds":round(seconds-old_seconds,6),
            "candidate_pcm_rate_hz":rate,"reference_pcm_rate_hz":old_rate,
            "review_state":"UNREVIEWED_CANDIDATE_ONLY","publication_allowed":False})
    # Verify all evidence before creating any outputs.
    dest.mkdir(parents=True)
    try:
        (dest/"original_scene_references").mkdir()
        (dest/"unapproved_trials").mkdir()
        for slide,ref in refs.items():
            dst=dest/"original_scene_references"/f"slide{slide:02d}_reference.wav"
            shutil.copyfile(ref,dst)
            if digest(dst)!=digest(ref):raise ReviewBundleError("Reference copy changed")
        for row in candidates:
            original=source/row["relative_path"]
            name=f"slide{row['slide']:02d}_{row['risk_class']}_UNREVIEWED.wav"
            dst=dest/"unapproved_trials"/name
            shutil.copyfile(original,dst)
            if digest(dst)!=row["wav_sha256"]:
                raise ReviewBundleError("QA candidate changed during copying")
        verify_workspace(stage)
        manifest={"schema_version":1,
          "status":"TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED",
          "source_slide_pdf_sha256":receipt["source_pdf_sha256"],
          "narration_sha256":receipt["narration_sha256"],
          "source_mp4_sha256":digest(source/"slides.mp4"),
          "legacy_scene_audio_only":True,
          "historical_audio_candidates":candidates,
          "slides_to_review":[5,6,10],
          "voice_consistency_verified":False,
          "phonetic_accuracy_verified":False,
          "word_level_highlighting_verified":False,
          "academic_quality_verified":False,
          "publication_allowed":False,"source_modified":False}
        atomic_json(dest/"review_manifest.json",manifest)
    except Exception:
        shutil.rmtree(dest)
        raise
    return {"review_dir":str(dest),"clips":len(candidates),
        "slides_to_review":[5,6,10],
        "provisional_references":len(refs),
        "approved_for_source_replacement":False,
        "source_modified":False}
