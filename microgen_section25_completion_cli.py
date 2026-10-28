"""Authoritative nonpublishing §2.5 full-lecture continuation CLI.

Drives existing independently staged, no-overwrite processing: prepare,
render, exact-source-PCM mux, verify all visual cues, audit. A successful
technical candidate is not an authenticated math/phonetic release.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from microgen_source_safe_orchestrator import digest,read_json,verify_workspace
from microgen_full17_render import create_full17_render_workspace,render_complete_full17
from microgen_full17_pcm_mux import remux_full_lecture_with_all_source_pcm
from microgen_full17_pixel_acceptance import check_all_full17_highlights

def collect_release_blockers(workspace,*,pixel_report):
    root=Path(workspace).resolve(strict=True)
    src=verify_workspace(root)
    part=read_json(root/"parts_receipt.json")
    full=read_json(root/"complete_decoded_pcm_candidate"/"full_pcm_candidate_receipt.json")
    cues=read_json(root/"cues.json")
    qa=read_json(pixel_report)
    if (full.get("status")!="COMPLETE_17_SLIDE_PCM_EXACT_TECHNICAL_CANDIDATE"
        or full.get("all_original_decoded_PCM_samples_preserved") is not True
        or full.get("publication_allowed") is not False
        or qa.get("publication_allowed") is not False
        or qa.get("candidate_video_sha256")!=full["video_sha256"]
        or qa.get("cue_count")!=len(cues["elements"])):
        raise ValueError("Technical source/visual acceptance receipts are inconsistent")
    video=Path(full["video_path"]).resolve(strict=True)
    if not video.is_file() or digest(video)!=full["video_sha256"]:
        raise ValueError("Final technical video changed")
    blockers=[
      "UNVERIFIED_ACTUAL_SPOKEN_WORD_TO_FORMULA_FIGURE_SEMANTICS",
      "UNVERIFIED_MATH_AND_FIGURE_ACADEMIC_CORRECTNESS",
      "PRONUNCIATION_C_DOT_SLIDE6_AND_Y_SLIDE10_UNVERIFIED",
      "CORRECTED_CLIP_SPEAKER_IDENTITY_NOT_AUTHENTICATED",
      "OFFLINE_ASR_WORD_TIMESTAMPS_NOT_INDEPENDENT_GROUND_TRUTH",
      "TECHNICAL_ALAC_MP4_NOT_VALIDATED_AS_DISTRIBUTION_FORMAT",
      "SOURCE_LECTURE_HAS_NOT_PASSED_INDEPENDENT_LISTENING_QA",
      "STACKED_DRAFT_PRS_NOT_REVIEWED_AND_MERGED",
    ]
    if qa.get("all_visual_cues_verified") is not True:
        blockers.append("PARTIAL_OR_MISSING_REAL_MP4_HIGHLIGHT_PIXELS")
    if not 0<full["video_seconds"]<600:
        blockers.append("MP4_NOT_STRICTLY_BELOW_600_SECONDS")
    return {
      "schema_version":1,
      "status":"COMPLETE_TECHNICAL_MEDIA_CANDIDATE_REQUIRES_ACADEMIC_AND_PHONETIC_QA",
      "source_root":src["source_root"],
      "candidate_video":str(video),
      "candidate_video_sha256":full["video_sha256"],
      "technical_mp4_seconds":full["video_seconds"],
      "source_audio_pcm_exact_match":full["all_original_decoded_PCM_samples_preserved"],
      "source_audio_tail_retained_seconds":full["preserved_audio_tail_seconds"],
      "source_slide_count":src["slide_count"],
      "source_word_cues":len(cues["elements"]),
      "source_word_cues_pixel_verified":qa.get("visual_cues_verified"),
      "release_blockers":blockers,
      "ready_for_publication":False,
      "publication_performed":False,
      "source_modified":False,
    }

def main(argv=None):
    parser=argparse.ArgumentParser(description="Source-safe original MicroGen_AI §2.5 production CLI")
    parser.add_argument("phase",choices=("prepare","render","pcm","pixels","audit"))
    parser.add_argument("--stage",required=True,type=Path)
    parser.add_argument("--manifest",type=Path)
    parser.add_argument("--ffmpeg",type=Path)
    parser.add_argument("--pixel-report",type=Path)
    args=parser.parse_args(argv)
    if args.phase=="prepare":
        if args.manifest is None:
            parser.error("--manifest required for prepare")
        result=create_full17_render_workspace(args.manifest,args.stage)
    elif args.phase=="render":
        if args.ffmpeg is None:parser.error("--ffmpeg required for render")
        result=render_complete_full17(args.stage,ffmpeg=str(args.ffmpeg))
    elif args.phase=="pcm":
        if args.ffmpeg is None:parser.error("--ffmpeg required for pcm")
        result=remux_full_lecture_with_all_source_pcm(args.stage,ffmpeg=str(args.ffmpeg))
    elif args.phase=="pixels":
        if args.ffmpeg is None or args.pixel_report is None:
            parser.error("--ffmpeg and --pixel-report required for pixels")
        result=check_all_full17_highlights(args.stage,args.pixel_report,
                                            ffmpeg=str(args.ffmpeg))
    else:
        if args.pixel_report is None:
            parser.error("--pixel-report required for audit")
        result=collect_release_blockers(args.stage,pixel_report=args.pixel_report)
    print(json.dumps(result,sort_keys=True,indent=2))
    return 2 if args.phase=="audit" and not result["ready_for_publication"] else 0

if __name__=="__main__":
    raise SystemExit(main())
