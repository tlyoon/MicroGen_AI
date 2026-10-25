"""Current corrected-lesson evidence gate, distinct from historic §2.5 gate.

Legacy acceptance was pinned before new ASR/PDF word cues and still listed
missing model and pixel-QA blockers after real technical passes. This
reconciles exact current artifacts without confusing ASR/pixels with correct
spoken maths, phonetics, speaker identity or publication consent.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from microgen_corrected_release_gate import audit_corrected_section25
from microgen_corrected_semantic_review import (
    _check_evidence,verify_semantic_packet_file_integrity
)
from microgen_source_safe_orchestrator import atomic_json,read_json,digest


class CorrectedCurrentGateError(ValueError):
    pass


def _review_unapproved(meta,source,cues,asr,video,plan,pixel_dir):
    if (meta.get("schema_version")!=1
            or meta.get("status")!="CORRECTED_MATH_FIGURE_SOURCE_BOUND_REVIEW_UNAPPROVED"
            or meta.get("source_pdf_sha256")!=plan["source"]["source_pdf_sha256"]
            or meta.get("narration_sha256")!=plan["source"]["narration_sha256"]
            or meta.get("corrected_asr_sha256")!=digest(asr)
            or meta.get("current_cues_sha256")!=digest(plan["stage"]/"cues.json")
            or meta.get("corrected_video_sha256")!=digest(video)
            or meta.get("corrected_pcm_sha256")!=plan["pcm"]["pcm_sha256"]
            or meta.get("word_overlay_pixel_receipt_sha256")!=
               digest(Path(pixel_dir)/"word_pixel_audit_receipt.json")
            or meta.get("slide_count")!=17
            or meta.get("corrected_audio_slides")!=17
            or meta.get("publication_allowed") is not False
            or meta.get("all_mathematical_semantics_verified") is not False
            or meta.get("all_figure_spoken_correspondence_verified") is not False
            or meta.get("pronunciation_approved") is not False
            or meta.get("speaker_identity_approved") is not False
            or not isinstance(meta.get("math_region_candidates"),int)
            or not isinstance(meta.get("figure_region_candidates"),int)
            or meta["unreviewed_region_decisions"]!=
               meta["math_region_candidates"]+meta["figure_region_candidates"]
            or len(meta.get("slides",[]))!=17):
        raise CorrectedCurrentGateError("Current academic packet not bound or falsely approved")
    return meta["unreviewed_region_decisions"]


def reconcile_corrected_lecture_release_evidence(
        *,recovery,stage,selection,shadow,old_video,old_pixel_audit,
          pronunciation_packet,asr,highlight_video,word_pixel_audit,
          semantic_review,expected_semantic_receipt_sha256,output):
    """Recheck whole original + current corrected stages and release *blockers*.

    A technical PASS can reduce obsolete infrastructure blockers, never
    eliminate independent human listening, math/figure or release controls.
    """
    plan,source,cues,asr_doc,words,script,movie,pixel=_check_evidence(
        stage,selection,shadow,asr,highlight_video,word_pixel_audit)
    reviewroot=Path(semantic_review).resolve(strict=True)
    if (not isinstance(expected_semantic_receipt_sha256,str)
            or len(expected_semantic_receipt_sha256)!=64):
        raise CorrectedCurrentGateError("Trusted external semantic receipt SHA required")
    packet_files=verify_semantic_packet_file_integrity(
        reviewroot,expected_receipt_sha256=expected_semantic_receipt_sha256)
    meta=read_json(reviewroot/"semantic_review_receipt.json")
    unreviewed=_review_unapproved(meta,source,cues,asr,movie,plan,word_pixel_audit)
    # No current stage review ever constitutes a phonetic/semantic verdict.
    if (pixel.get("publication_allowed") is not False
            or pixel.get("actual_overlay_pixels_verified") is not True
            or pixel.get("failed_samples")!=0
            or pixel.get("expected_cues")!=len(cues["elements"])
            or pixel.get("positive_samples")!=len(cues["elements"])
            or not pixel.get("post_cue_control_samples",0)>0
            or any(x.get("publication_allowed") is True
                   for x in (meta,cues,asr_doc))):
        raise CorrectedCurrentGateError("Spoken/word overlay evidence not valid")
    output=Path(output).resolve(strict=False)
    protected=[source,plan["stage"],Path(recovery).resolve(strict=True),
               Path(selection).resolve(strict=True),Path(shadow).resolve(strict=True),
               Path(old_video).resolve(strict=True),
               Path(old_pixel_audit).resolve(strict=True),
               Path(pronunciation_packet).resolve(strict=True),
               Path(highlight_video).resolve(strict=True),
               Path(word_pixel_audit).resolve(strict=True),
               reviewroot,Path(asr).resolve(strict=True).parent]
    if (output.exists() or output.is_symlink()
            or any(output==p or output.is_relative_to(p) or p.is_relative_to(output)
                   for p in protected)):
        raise CorrectedCurrentGateError("New isolated gate folder required")
    output.mkdir(parents=True,exist_ok=False)
    try:
        baseline_path=output/"historical_gate_proof_NOT_CURRENT.json"
        baseline=audit_corrected_section25(
            recovery=recovery,corrected_stage=stage,
            selection=selection,shadow=shadow,
            slide_video=old_video,pixel_audit=old_pixel_audit,
            listening_packet=pronunciation_packet,
            output=baseline_path)
        earlier=read_json(baseline_path)
        if (baseline.get("publication_allowed") is not False
                or earlier.get("publication_allowed") is not False
                or earlier.get("ready_to_publish") is not False
                or earlier.get("full_corrected_pcm_sample_integrity_verified") is not True
                or earlier.get("slide_level_visual_mapping_verified") is not True
                or earlier.get("corrected_pcm_sha256")!=plan["pcm"]["pcm_sha256"]
                or earlier.get("original_pdf_sha256")!=plan["source"]["source_pdf_sha256"]
                or earlier.get("pixel_matches")!=50):
            raise CorrectedCurrentGateError("Historical upstream candidate lacks real proof")
        # Verified technical properties and remaining substantive acceptance
        # are deliberately separate. Do not import stale v1 hard-coded blockers.
        blockers=[
            "CORRECTED_C_AND_Y_PRONUNCIATION_REQUIRES_INDEPENDENT_LISTENING",
            "NARRATOR_IDENTITY_AND_VOICE_CONSISTENCY_UNVERIFIED",
            "SPOKEN_MATHEMATICAL_EQUATION_CORRESPONDENCE_UNREVIEWED",
            "SPOKEN_GRAPH_FIGURE_LABEL_AND_PANEL_MAPPING_UNREVIEWED",
            "TIMED_PDF_WORD_PIXELS_NOT_PROOF_OF_SPOKEN_MATH_ELEMENT_SEMANTICS",
            "INDEPENDENT_ACADEMIC_AND_FULL_LESSON_AUDIO_LISTENING_QA_NOT_DONE",
            "STACKED_DRAFT_INTEGRATION_AND_PUBLICATION_AUTHORIZATION_PENDING",
        ]
        result={
            "schema_version":2,
            "status":"SOURCE_BOUND_CORRECTED_TECHNICAL_PASS_DOMAIN_RELEASE_BLOCKED",
            "source_pdf_sha256":plan["source"]["source_pdf_sha256"],
            "script_sha256":plan["source"]["narration_sha256"],
            "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
            "corrected_highlight_video_sha256":digest(movie),
            "corrected_asr_sha256":digest(asr),
            "corrected_cues_sha256":digest(plan["stage"]/"cues.json"),
            "verified_semantic_packet_receipt_sha256":expected_semantic_receipt_sha256,
            "historical_baseline_gate_sha256":digest(baseline_path),
            "technical_evidence":{
                "corrected_audio_slide_sha_count":len(plan["segments"]),
                "source_pdf_slide_count":plan["source"]["slide_count"],
                "full_corrected_pcm_sha_bound":True,
                "highlight_video_seconds":read_json(
                    Path(highlight_video)/"word_highlight_candidate_receipt.json")[
                        "duration_seconds"],
                "historical_pdf_slide_pixel_samples":earlier["pixel_matches"],
                "current_word_cue_candidates":len(cues["elements"]),
                "actual_current_word_pixels_passed":pixel["positive_samples"],
                "post_cue_controls_passed":pixel["post_cue_control_samples"],
                "semantic_packet_files_sha_checked":packet_files["files_checked"]
            },
            "domain_approval":{
                "math_region_candidates_unreviewed":meta["math_region_candidates"],
                "figure_region_candidates_unreviewed":meta["figure_region_candidates"],
                "total_math_figure_region_decisions_unreviewed":unreviewed,
                "phonetic_c_and_y_independently_verified":False,
                "single_narrator_independently_verified":False,
                "math_equation_spoken_correspondence_verified":False,
                "figure_audio_correspondence_verified":False,
                "academic_and_listening_review_complete":False
            },
            "release_blockers":blockers,
            "publication_allowed":False,"ready_to_publish":False,
            "historical_source_media_modified":False
        }
        # Review packet unchanged while consolidating statuses.
        if (digest(reviewroot/"semantic_review_receipt.json")!=
                expected_semantic_receipt_sha256
                or digest(movie)!=result["corrected_highlight_video_sha256"]
                or digest(asr)!=result["corrected_asr_sha256"]):
            raise CorrectedCurrentGateError("Release evidence mutated during validation")
        atomic_json(output/"corrected_release_status_v2.json",result)
        return {"technical_pass":True,"pending_review":unreviewed,
                "release_blockers":len(blockers),"publication_allowed":False,
                "report":str(output/"corrected_release_status_v2.json")}
    except Exception:
        shutil.rmtree(output)
        raise
