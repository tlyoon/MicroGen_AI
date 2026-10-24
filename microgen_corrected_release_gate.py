"""Independent corrected-lesson release dossier. It can NEVER authorize publication.

The previous final evidence gate covers the historic original-audio MP4;
this gates the *corrected* 17-WAV/PDF/pixel/listening chain instead.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,verify_workspace
from microgen_corrected_slide_clock import build_slide_clock,CorrectedSlidesError
from microgen_corrected_shadow_video import _pcm_properties
from microgen_audio_cue_binding import validate_audio_bound_cues

class CorrectedReleaseGateError(ValueError):
    pass

def audit_corrected_section25(*,recovery,corrected_stage,selection,shadow,
                              slide_video,pixel_audit,listening_packet,
                              output,offline_model=None):
    recovered=Path(recovery).resolve(strict=True)
    stage=Path(corrected_stage).resolve(strict=True)
    chosen=Path(selection).resolve(strict=True)
    sh=Path(shadow).resolve(strict=True)
    vid=Path(slide_video).resolve(strict=True)
    pix=Path(pixel_audit).resolve(strict=True)
    review=Path(listening_packet).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    src=verify_workspace(recovered)
    plan=build_slide_clock(stage,chosen,sh)
    source=Path(src["source_root"]).resolve(strict=True)
    protected=(source,recovered,stage,chosen,sh,vid,pix,review)
    if (dest.exists() or dest.is_symlink() or
            any(dest==p or dest.is_relative_to(p) or p.is_relative_to(dest) for p in protected)):
        raise CorrectedReleaseGateError("Evidence output must be new and isolated")
    if plan["source"]!=src:
        raise CorrectedReleaseGateError("Original and corrected source mismatch")
    video=vid/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4"
    shadow_wav=plan["shadow_wav"]
    v=read_json(vid/"corrected_slide_clock_receipt.json")
    px=read_json(pix/"pixel_audit_receipt.json")
    rp=read_json(review/"listening_packet_receipt.json")
    if (video.is_symlink() or not video.is_file() or
            v.get("status")!="CORRECTED_SLIDE_CLOCK_NOT_SEMANTICALLY_APPROVED" or
            v.get("publication_allowed") is not False or
            v.get("word_highlights_present") is not False or
            v.get("video_sha256")!=digest(video) or
            v.get("source_pdf_sha256")!=src["source_pdf_sha256"] or
            v.get("shadow_wav_sha256")!=digest(shadow_wav) or
            v.get("slides")!=plan["segments"] or
            v.get("pcm_sha256_verified")!=plan["pcm"]["pcm_sha256"] or
            not 0<v.get("audio_seconds",0)<600 or
            abs(v["audio_seconds"]-plan["audio_seconds"])>.01):
        raise CorrectedReleaseGateError("Corrected technical MP4 unbound or altered")
    if (px.get("status")!="CORRECTED_SLIDE_PIXEL_AUDIT_PASS_NOT_ACADEMIC" or
            px.get("publication_allowed") is not False or
            px.get("slide_mapping_technically_verified") is not True or
            px.get("sample_count")!=50 or px.get("passed_samples")!=50 or
            px.get("video_sha256")!=digest(video) or
            px.get("source_pdf_sha256")!=src["source_pdf_sha256"] or
            px.get("source_shadow_wav_sha256")!=digest(shadow_wav) or
            len(px.get("samples",[]))!=50 or
            any(row.get("correct_pdf_match") is not True for row in px["samples"])):
        raise CorrectedReleaseGateError("Missing or compromised 50-frame source pixel QA")
    if (rp.get("status")!="SOURCE_BOUND_PRONUNCIATION_AB_REVIEW_UNAPPROVED" or
            rp.get("publication_allowed") is not False or
            rp.get("phonetic_correctness_verified") is not False or
            rp.get("voice_consistency_verified") is not False or
            rp.get("source_pdf_sha256")!=src["source_pdf_sha256"] or
            rp.get("script_sha256")!=src["narration_sha256"] or
            rp.get("source_video_sha256")!=digest(video) or
            rp.get("pixel_audit_sha256")!=digest(pix/"pixel_audit_receipt.json") or
            sorted(row.get("slide") for row in rp.get("pairs",[]))!=[5,6,10]):
        raise CorrectedReleaseGateError("Original/corrected source-bound listening packet untrusted")
    for row in rp["pairs"]:
        i=row["slide"]
        for kind,key in (("original","original_sha"),("trial","corrected_sha")):
            ref=review/f"slide{i:02d}_{kind}_UNREVIEWED.wav"
            if ref.is_symlink() or not ref.is_file() or digest(ref)!=row[key]:
                raise CorrectedReleaseGateError("Review WAV altered since source proof")
    cues=stage/"cues.json"
    acoustic_prepared=False
    if cues.exists():
        if cues.is_symlink() or not cues.is_file():
            raise CorrectedReleaseGateError("Linked or invalid ASR cues")
        # Structural SHA-bound candidate is not independent pronunciation QA.
        validate_audio_bound_cues(stage,read_json(cues))
        acoustic_prepared=True
    model=Path(offline_model).resolve(strict=False) if offline_model is not None else None
    vosk_importable=importlib.util.find_spec("vosk") is not None
    model_present=bool(model is not None and model.is_dir() and
                       not model.is_symlink() and (model/"am").is_dir())
    blockers=[
        "C_AND_Y_VARIABLE_CORRECTED_TRIALS_REQUIRE_INDEPENDENT_LISTENING",
        "SINGLE_NARRATOR_VOICE_IDENTITY_NOT_VERIFIED",
        "MATHEMATICAL_EQUATION_AND_FIGURE_SPOKEN_SEMANTICS_NOT_APPROVED",
        "INDEPENDENT_ACADEMIC_AND_AUDIO_LISTENING_QA_NOT_COMPLETE",
        "CORRECTED_WORD_LEVEL_HIGHLIGHT_PIXELS_NOT_VERIFIED",
        "DRAFT_PR_STACK_NOT_INTEGRATED_OR_RELEASE_APPROVED",
    ]
    if not acoustic_prepared:
        blockers.append("FRESH_SHA_BOUND_17_SLIDE_ASR_CUES_NOT_GENERATED")
    else:
        blockers.append("CANDIDATE_ASR_WORD_CUES_REQUIRE_INDEPENDENT_ACOUSTIC_SEMANTIC_QA")
    if not (vosk_importable and model_present):
        blockers.append("OFFLINE_ASR_PYTHON_PACKAGE_OR_EXPLICIT_MODEL_UNAVAILABLE")
    if digest(video)!=v["video_sha256"] or verify_workspace(recovered)!=src:
        raise CorrectedReleaseGateError("Source changed during final dossier preflight")
    verdict={"schema_version":1,"status":"CORRECTED_17_SLIDE_TECHNICALLY_VERIFIED_RELEASE_BLOCKED",
             "original_pdf_sha256":src["source_pdf_sha256"],
             "original_narration_sha256":src["narration_sha256"],
             "corrected_video_sha256":digest(video),
             "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
             "duration_seconds":v["audio_seconds"],
             "slide_count":17,"pixel_matches":px["passed_samples"],
             "corrected_trial_slides":[5,6,10],
             "slide_level_visual_mapping_verified":True,
             "full_corrected_pcm_sample_integrity_verified":True,
             "candidate_word_cues_structurally_bound":acoustic_prepared,
             "offline_vosk_importable":vosk_importable,
             "explicit_model_directory_present":model_present,
             "human_listening_verdict_provided":False,
             "math_figure_semantics_verified":False,"voice_verified":False,
             "phonetic_correctness_verified":False,
             "release_blockers":blockers,
             "publication_allowed":False,"ready_to_publish":False,
             "original_media_modified":False}
    atomic_json(dest,verdict)
    return {"status":verdict["status"],"slide_pixels":px["passed_samples"],
            "release_blockers":len(blockers),
            "publication_allowed":False,"report":str(dest)}
