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
    from microgen_timed_highlight_contract import MANIFEST,inspect_timed_highlights
    if (stage/MANIFEST).exists():
        timings=inspect_timed_highlights(stage)
        if timings["slide_count"]!=count:
            raise AutonomousAcceptanceError("Timed source-cue count mismatch")
        from microgen_measured_highlight_video_qa import RECEIPT as VISUAL_RECEIPT
        if not (stage/VISUAL_RECEIPT).is_file() or (stage/VISUAL_RECEIPT).is_symlink():
            raise AutonomousAcceptanceError(
                "Missing independent visual highlight receipt for timed lecture")
        names.append(VISUAL_RECEIPT)
        names.append(MANIFEST)
        rows=json.loads((stage/MANIFEST).read_text(encoding="utf8"))["slides"]
        names += [cue["audio_chunk"] for row in rows for cue in row["cues"]]
    if len(names)!=len(set(names)):
        raise AutonomousAcceptanceError("Duplicate or ambiguous acceptance assets")
    return {name:sha256(stage/name) for name in names}


def _verified_timed_visual(stage:Path, count:int)->dict | None:
    """Require independent decoded-video evidence for a measured-cue lecture.

    Unchanged static lectures do not acquire new approval requirements.
    This is a *visual* technical gate: it does not certify spoken phonemes,
    mathematics, scientific semantics, or textbook publication rights.
    """
    from microgen_timed_highlight_contract import MANIFEST
    manifest=stage/MANIFEST
    if manifest.is_symlink():
        raise AutonomousAcceptanceError("Unsafe timed-cue manifest link")
    if not manifest.exists():
        return None
    from microgen_measured_highlight_video_qa import verify_receipt as verify_visual
    from microgen_runtime_preflight import find_h264_ffmpeg

    ffmpeg=os.environ.get("MICROVID_FFMPEG") or find_h264_ffmpeg()
    if not ffmpeg or not Path(ffmpeg).is_file():
        raise AutonomousAcceptanceError("Timed lecture lacks decoded-frame QA tool")
    try:
        report=verify_visual(stage,ffmpeg=Path(ffmpeg))
    except (RuntimeError, ValueError, OSError, TypeError, KeyError) as exc:
        raise AutonomousAcceptanceError(
            "Timed lecture requires independently verified visual QA receipt"
        ) from exc
    if (not isinstance(report,dict) or
            report.get("status")!=
                "SOURCE_PCM_TIMED_VISUAL_HIGHLIGHTS_INDEPENDENTLY_CHECKED" or
            report.get("slide_count")!=count or
            type(report.get("cue_count")) is not int or
            report["cue_count"]<1 or
            not isinstance(report.get("checked_cues"),list) or
            len(report["checked_cues"])!=report["cue_count"] or
            report.get("visual_highlight_rendering_verified") is not True or
            report.get("spoken_word_to_element_alignment_verified") is not False or
            report.get("academic_correctness_verified") is not False or
            report.get("publication_allowed") is not False):
        raise AutonomousAcceptanceError(
            "Timed visual QA does not establish the declared private evidence")
    return report


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
    timed_visual=_verified_timed_visual(stage,count)
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
    evidence={
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
    # Preserve the byte-for-byte legacy static acceptance shape. Old private
    # receipts remain valid, but measured-cue stages need a new, bound field.
    if timed_visual is not None:
        evidence["timed_visual_highlight_qa"]={
            "status":timed_visual["status"],
            "cue_count":timed_visual["cue_count"],
            "visual_highlight_rendering_verified":True,
            "spoken_word_to_element_alignment_verified":False,
            "publication_allowed":False,
        }
    return evidence


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
