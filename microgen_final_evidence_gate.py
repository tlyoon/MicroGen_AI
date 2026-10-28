"""Fail-closed §2.5 full development evidence gate.

Technical MP4 success cannot satisfy independently missing voice, phonetic,
mathematical and semantic approval. This module has no publish or write-back.
"""
from pathlib import Path
from microgen_source_safe_orchestrator import verify_workspace,digest,read_json,atomic_json,OrchestratorError

class FinalEvidenceError(OrchestratorError):
    pass

def audit_complete_section25(*,original_recovery,full_video_stage,
    phonetic_risks,shadow_audio,shadow_seams,math_regions,figure_regions,
    math_anchors,figure_crops,independent_packet,full_video_pixels,
    output):
    root=Path(original_recovery).resolve(strict=True)
    source=verify_workspace(root)
    orig=Path(source["source_root"]).resolve(strict=True)
    stage=Path(full_video_stage).resolve(strict=True)
    final_workspace=verify_workspace(stage)
    if (final_workspace["source_pdf_sha256"]!=source["source_pdf_sha256"] or
        final_workspace["narration_sha256"]!=source["narration_sha256"]):
        raise FinalEvidenceError("Whole lesson source bindings differ")
    dest=Path(output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest.is_relative_to(orig)
        or dest.is_relative_to(root) or dest.is_relative_to(stage)):
        raise FinalEvidenceError("No output replacement or protected writes")
    entries={
      "phonetic":read_json(phonetic_risks),
      "shadow":read_json(Path(shadow_audio)/"shadow_receipt.json"),
      "seams":read_json(shadow_seams),
      "math":read_json(math_regions),
      "figure":read_json(figure_regions),
      "anchor":read_json(math_anchors),
      "crop":read_json(Path(figure_crops)/"pixel_review_manifest.json"),
      "review":read_json(Path(independent_packet)/"review_index.json"),
      "visual":read_json(full_video_pixels),
      "lossless":read_json(stage/"complete_decoded_pcm_candidate"/"full_pcm_candidate_receipt.json"),
      "delivery":read_json(stage/"standard_h264_aac_candidate"/"format_receipt.json"),
    }
    k=source["source_pdf_sha256"];n=source["narration_sha256"]
    if (any(entries[p].get("source_pdf_sha256")!=k for p in
            ("math","figure","anchor","crop","review")) or
        entries["phonetic"].get("narration_sha256")!=n or
        entries["review"].get("source_narration_sha256")!=n or
        entries["delivery"].get("original_lossless_candidate_sha256")!=entries["lossless"]["video_sha256"] or
        entries["visual"].get("candidate_video_sha256")!=entries["lossless"]["video_sha256"]):
        raise FinalEvidenceError("Cross-stage source fingerprint drift")
    if (entries["review"].get("total_slides")!=17 or
        entries["visual"].get("cue_count")!=66 or
        entries["lossless"].get("all_original_decoded_PCM_samples_preserved") is not True or
        entries["delivery"].get("candidate_video_seconds",601)>=600):
        raise FinalEvidenceError("Full-video critical technical proof incomplete")
    for title in ("phonetic","shadow","seams","math","figure","anchor",
                  "crop","review","visual","lossless","delivery"):
        if entries[title].get("publication_allowed") is not False:
            raise FinalEvidenceError("Unsupported release approval in evidence")
    candidate=Path(entries["delivery"]["candidate_mp4_path"]).resolve(strict=True)
    if (candidate.is_symlink() or digest(candidate)!=entries["delivery"]["candidate_mp4_sha256"]):
        raise FinalEvidenceError("H264/AAC candidate changed")
    risks=[
       "LEGACY_C_DOT_AND_Y_VARIABLE_PHONETICS_NEED_INDEPENDENT_LISTENING",
       "CORRECTED_SHADOW_SPEAKER_IDENTITY_NOT_VERIFIED",
       "SHADOW_SEAM_ACOUSTIC_DIFFERENCES_NEED_REVIEW",
       "REPLACEMENT_SLIDE_TIMING_REQUIRES_NEW_FORCED_ALIGNMENT",
       "ONE_CONTEXTUAL_MATH_PHRASE_CANNOT_COVER_FULL_LECTURE_EQUATIONS",
       "FIGURE_CAPTIONS_AND_GEOMETRY_NOT_ACADEMICALLY_CERTIFIED",
       "66_TEXT_PIXEL_CUES_ARE_NOT_COMPLETE_FORMULA_FIGURE_SYNC",
       "STANDARD_AAC_DELIVERY_TECHNICALLY_VALID_NOT_RELEASE_APPROVED",
       "INDEPENDENT_ACADEMIC_AND_HUMAN_LISTENING_QA_MISSING",
       "STACKED_DRAFT_PRS_REQUIRE_INTEGRATION_REVIEW",
    ]
    if digest(orig/"slides.pdf")!=k:raise FinalEvidenceError("Original PDF changed")
    doc={"schema_version":1,"status":"TECHNICAL_VIDEO_COMPLETE_ACADEMIC_RELEASE_BLOCKED",
       "original_pdf_sha256":k,"original_narration_sha256":n,
       "source_video_sha256":entries["lossless"]["source_mp4_sha256"],
       "technical_h264_aac_sha256":digest(candidate),
       "technical_duration_seconds":entries["delivery"]["candidate_video_seconds"],
       "technical_source_pcm_exact_lossless_copy":True,
       "visible_word_cues_verified":entries["visual"]["visual_cues_verified"],
       "legacy_phonetic_observations":len(entries["phonetic"]["risks"]),
       "shadow_acoustic_seams_flagged":entries["seams"]["flagged_loudness_joins"],
       "math_expression_regions":entries["math"]["candidate_regions"],
       "candidate_figure_regions":entries["figure"]["figure_candidates"],
       "spoken_math_contextual_anchors":entries["anchor"]["proposed"],
       "review_packet_slides":entries["review"]["total_slides"],
       "outstanding_release_requirements":risks,
       "human_academic_and_listening_approval_observed":False,
       "publishable":False,"publication_allowed":False,
       "original_media_modified":False}
    atomic_json(dest,doc)
    return {"technical_video_complete":True,
       "release_blockers":len(risks),
       "audio_visual_math_certified":False,
       "publication_allowed":False,
       "report":str(dest)}
