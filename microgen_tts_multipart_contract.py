"""Read-only multipart topic AV QA; no automatic media edits or publication."""
from __future__ import annotations
from pathlib import Path
from microgen_tts_video_duration_inventory import audit_videos

class MultipartContractError(ValueError):pass
def audit_topic_parts(parts:list[dict],*,max_parts:int=20)->dict:
    if (not isinstance(parts,list) or not parts or
        type(max_parts)!=int or not 1<=max_parts<=40 or len(parts)>max_parts):
        raise MultipartContractError("Invalid bounded topic part plan")
    ordered=[];seen=set()
    for i,item in enumerate(parts,1):
        if not isinstance(item,dict) or item.get("part_number")!=i:
            raise MultipartContractError("Topic parts must be consecutively ordered from 1")
        name=item.get("video")
        if not isinstance(name,str) or not name:
            raise MultipartContractError("Missing topic-part video location")
        path=Path(name).resolve(strict=True)
        if path in seen:raise MultipartContractError("Repeated topic video part")
        seen.add(path);ordered.append(path)
    result=audit_videos(ordered)
    hashes=[x["video_sha256"] for x in result["videos"]]
    repeated_bytes=len(hashes)!=len(set(hashes))
    return {"schema_version":1,"part_count":len(parts),
        "parts":result["videos"],"all_parts_below_600_seconds":result["all_videos_under_600_seconds"],
        "distinct_part_content":not repeated_bytes,
        "multipart_technical_duration_pass":result["all_videos_under_600_seconds"] and not repeated_bytes,
        "narration_element_highlights_verified":False,
        "academic_quality_verified":False,"publication_performed":False,
        "further_action":"SPLIT_LONG_PARTS" if not result["all_videos_under_600_seconds"] else
            "INVESTIGATE_DUPLICATE_PARTS" if repeated_bytes else
            "CHECK_UNPROVEN_SYNC_AND_ACADEMIC_PROPERTIES"}
