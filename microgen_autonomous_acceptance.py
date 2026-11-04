"""Unified autonomous, source-and-media-bound PRIVATE technical acceptance.

The gate is evidence-based and read-only except for its own new receipt. It
requires independent model-based source consistency screening, independent
two-model acoustic evidence, PCM/voice provenance, figure-crop provenance and
verified final H264/AAC media with every delivered MP4 part <600 seconds.

No human sign-off is required in the software development loop, but the
receipt NEVER grants textbook redistribution rights, certifies perfect
mathematics/phonetics or automatically uploads to external destinations.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from microgen_quality import (
    QualityError,sha256,check_slide_pdf,check_graphics,
    check_narration,check_wavs,check_video,numbered_files,
)

RECEIPT=".microgen_autonomous_acceptance.json"
SCHEMA=1


class AutonomousAcceptanceError(QualityError):
    pass


def _snap(stage:Path, count:int)->dict[str,str]:
    names=["source.pdf","slides.pdf","slides.tex",
           "script.txt","script_tts.json","slides.mp4",
           ".microgen_autonomous_science_qa.json",
           ".microgen_autonomous_acoustic_qa.json",
           ".microgen_tts_provenance.json"]
    names += [f"slide{i}.wav" for i in range(1,count+1)]
    names += [f"slide{i}.pdf" for i in range(1,count+1)]
    names += sorted(x.name for x in stage.glob("Figure*.png") if x.is_file())
    if (stage/"figure_composition_receipt.json").is_file():
        names.append("figure_composition_receipt.json")
    if (stage/".microgen_autonomous_parts.json").is_file():
        names.append(".microgen_autonomous_parts.json")
        names += sorted(x.name for x in stage.glob("slides_part_*.mp4") if x.is_file())
    if (stage/".microgen_multipart_receipt.json").is_file():
        names.append(".microgen_multipart_receipt.json")
        names += sorted(x.name for x in stage.glob("slides_part_*.mp4") if x.is_file())
    if len(names)!=len(set(names)):
        raise AutonomousAcceptanceError("Duplicate or ambiguous acceptance assets")
    return {name:sha256(stage/name) for name in names}


def inspect_stage(stage:Path)->dict:
    """Recalculate all technical requirements; no model calls or file writes."""
    from microgen_autonomous_science_qa import verify_receipt as science
    from microgen_autonomous_acoustic_gate import verify_receipt as acoustic
    from microgen_tts_release_audit import audit_stage as tts_audit
    from microgen_figure_composition import (
        validate_figure_receipt,audit_unmapped_source_crops)
    from microgen_tts_release_policy import AUTONOMOUS
    stage=Path(stage)
    if not stage.is_dir() or stage.is_symlink():
        raise AutonomousAcceptanceError("Stage must be an isolated real directory")
    before=hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest()
    deck=check_slide_pdf(stage/"slides.pdf",require_footer=True)
    count=deck["pages"]
    if not 1<=count<=200:
        raise AutonomousAcceptanceError("Invalid lecture slide count")
    check_graphics(stage/"slides.tex")
    narration=check_narration(stage/"script.txt",stage/"script_tts.json",count)
    wavs=check_wavs(stage,count)
    numbered_files(stage,"pdf",count)
    science_receipt=science(stage)
    acoustic_receipt=acoustic(stage)
    if science_receipt["slide_count"]!=count or acoustic_receipt["slide_count"]!=count:
        raise AutonomousAcceptanceError("Scientific/acoustic evidence slide-count mismatch")
    if science_receipt["unresolved_blocking_issues"]:
        raise AutonomousAcceptanceError("Unresolved scientific claim")
    if acoustic_receipt["independent_report"]["review_required_slides"]:
        raise AutonomousAcceptanceError("Unresolved acoustic mismatch")
    source_figures=validate_figure_receipt(stage)
    unmapped=audit_unmapped_source_crops(stage,receipt=source_figures)
    video=check_video(stage/"slides.mp4",expected_seconds=wavs["total_seconds"])
    parts=[]
    if video["seconds"]>=600:
        from microgen_autonomous_video_parts import verify_receipt as verify_parts
        receipt=verify_parts(stage)
        parts=receipt["parts"]
        if not parts or any(p["actual_seconds"]>=600 for p in parts):
            raise AutonomousAcceptanceError("Missing compliant final video segments")
    acoustic_report=acoustic_receipt["independent_report"]
    release=tts_audit(stage,acoustic_report=acoustic_report,qa_policy=AUTONOMOUS)
    if not release["automated_technical_qa_passed"]:
        raise AutonomousAcceptanceError(
            "Strict automatic AV/TTS blockers: "+", ".join(
                release["technical_blockers"]))
    if release["manual_approval_is_gate"]:
        raise AutonomousAcceptanceError("Manual certification has been made a gate")
    source_after=hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest()
    if source_after!=before:
        raise AutonomousAcceptanceError("Source changed during technical QA")
    return {
        "slide_count":count,
        "source_sha256":before,
        "scientific_screen_status":science_receipt["status"],
        "scientific_advisory_slide_count":science_receipt["advisory_slide_count"],
        "acoustic_screen_status":acoustic_receipt["status"],
        "acoustic_recognition_models":acoustic_receipt["recognition_models"],
        "repaired_wav_slide_count":acoustic_receipt["repaired_audio_slides"],
        "mapped_source_figure_count":len(source_figures["figures"]),
        "unmapped_source_crop_count":len(unmapped),
        "total_wav_seconds":wavs["total_seconds"],
        "complete_video_seconds":video["seconds"],
        "deliverable_video_parts":[{"file":p["file"],"slide_count":len(p["slides"]),
                                    "seconds":p["actual_seconds"]}
                                   for p in parts],
        "accepted_media_count":len(parts) if parts else 1,
        "production_quality_checks":release["checks"],
        "unproven_quality_dimensions":release["unproven_quality_dimensions"],
        "scope":"source-grounded automated TECHNICAL screening only",
        "scientific_correctness_certain":False,
        "pronunciation_perfection_certified":False,
        "copyright_distribution_authorized":False,
        "human_approval_required":False,
        "publication_allowed":False,
    }


def _accepted(record:dict)->bool:
    return (record.get("schema_version")==SCHEMA and
            record.get("status")=="PRIVATE_AUTONOMOUS_TECHNICAL_ACCEPTANCE_PASSED" and
            record.get("human_approval_required") is False and
            record.get("publication_allowed") is False and
            record.get("copyright_distribution_authorized") is False)


def verify_receipt(stage:Path)->dict:
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.is_file() or path.is_symlink():
        raise AutonomousAcceptanceError("Missing or unsafe private acceptance receipt")
    record=json.loads(path.read_text(encoding="utf8"))
    if not _accepted(record):
        raise AutonomousAcceptanceError("Invalid acceptance status or falsely granted rights")
    evidence=inspect_stage(stage)
    if record.get("evidence")!=evidence:
        raise AutonomousAcceptanceError("Independent QA evidence changed since receipt")
    if record.get("input_hashes")!=_snap(stage,evidence["slide_count"]):
        raise AutonomousAcceptanceError("Input artifacts drifted after acceptance")
    return record


def audit_stage(stage:Path)->dict:
    """New immutable private receipt only after all independent checks pass."""
    stage=Path(stage)
    path=stage/RECEIPT
    if path.exists() or path.is_symlink():
        return verify_receipt(stage)
    evidence=inspect_stage(stage)
    snapshot=_snap(stage,evidence["slide_count"])
    # Double-check against concurrent source/audio modifications.
    second=inspect_stage(stage)
    if evidence!=second or snapshot!=_snap(stage,evidence["slide_count"]):
        raise AutonomousAcceptanceError("Source/output changed during acceptance")
    record={
        "schema_version":SCHEMA,
        "status":"PRIVATE_AUTONOMOUS_TECHNICAL_ACCEPTANCE_PASSED",
        "human_approval_required":False,
        "publication_allowed":False,
        "copyright_distribution_authorized":False,
        "input_hashes":snapshot,
        "evidence":evidence,
        "producer":"MicroGen_AI original autonomous acceptance",
        "claims_restricted_to_actual_automated_checks":True,
    }
    with path.open("x",encoding="utf8") as f:
        f.write(json.dumps(record,indent=2,ensure_ascii=False))
    try:
        verify_receipt(stage)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return record


def main()->int:
    import sys
    if len(sys.argv)!=1:
        raise SystemExit("Run the private acceptance stage from its isolated work directory")
    record=audit_stage(Path.cwd())
    print(json.dumps({
        "status":record["status"],
        "slide_count":record["evidence"]["slide_count"],
        "accepted_media_count":record["evidence"]["accepted_media_count"],
        "human_approval_required":False,
        "publication_allowed":False},ensure_ascii=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
