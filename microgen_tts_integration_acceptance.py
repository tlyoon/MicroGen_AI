"""Integrated, read-only draft-stack and lecture-video *subset* acceptance.

Passing local commit lineage, policy truth table, and video duration NEVER
certifies true spoken phonemes, academic validity, or element highlighting.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_tts_stack_audit import audit_stack
from microgen_tts_release_matrix import verify_release_matrix
from microgen_tts_video_duration_inventory import audit_videos

def audit_integration(checkout:Path,base_sha:str,head_sha:str,
                      videos:list[Path])->dict:
    ancestry=audit_stack(checkout,base_sha,head_sha,max_commits=100)
    policy=verify_release_matrix()
    video=audit_videos(videos)
    accepted=ancestry["status"]=="LINEAR_DRAFT_ANCESTRY_VERIFIED" and \
              policy["policy_contract_consistent"] and \
              video["all_videos_under_600_seconds"]
    return {"schema_version":1,
            "integration_subset_verified":accepted,
            "status":"TECHNICAL_SUBSET_VERIFIED" if accepted
                     else "TECHNICAL_SUBSET_BLOCKED",
            "stack":ancestry,"release_policy_truth_table":policy,
            "video_duration_inventory":video,
            "phonetic_correctness_certified":False,
            "academic_or_figure_quality_certified":False,
            "element_highlight_sync_certified":False,
            "ci_result_for_head_commit_verified_by_this_tool":False,
            "ready_for_publication":False,
            "manual_signoff_gate_required":False,
            "assets_modified":False,"publication_performed":False,
            "next_required_evidence":"Independent verified phoneme labels and synchronized highlight checks"}
def main(argv=None):
    p=argparse.ArgumentParser(description="Nonpublishing integration subset audit")
    p.add_argument("checkout",type=Path)
    p.add_argument("base_sha");p.add_argument("head_sha")
    p.add_argument("videos",type=Path,nargs="+")
    args=p.parse_args(argv)
    report=audit_integration(args.checkout,args.base_sha,args.head_sha,args.videos)
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report["integration_subset_verified"] else 2
if __name__=="__main__":raise SystemExit(main())
