"""Read-only video duration and AV stream inventory for unattended teaching QA."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_quality import check_video,QualityError,sha256

class DurationInventoryError(ValueError):pass
def audit_videos(paths:list[Path],*,strict_limit:float=600)->dict:
    if (not isinstance(paths,list) or not paths or len(paths)>80 or
        not isinstance(strict_limit,(int,float)) or strict_limit!=600):
        raise DurationInventoryError("Explicit list and strict 600-second limit required")
    rows=[];seen=set()
    for p in paths:
        source=Path(p).resolve(strict=True)
        if source in seen:raise DurationInventoryError("Duplicate video in inventory")
        seen.add(source)
        before=sha256(source)
        try:
            details=check_video(source)
            sec=float(details["seconds"])
            if not (0<sec<strict_limit):
                reason="NOT_STRICTLY_UNDER_600_SECONDS"
            else:reason=None
        except (QualityError,OSError,ValueError,RuntimeError):
            sec=None;reason="AV_STREAM_VERIFICATION_FAILED"
        if sha256(source)!=before:
            raise DurationInventoryError("Video changed during read-only validation")
        rows.append({"video_sha256":before,"duration_seconds":sec,
                     "technical_duration_pass":reason is None,
                     "blocking_defect":reason,
                     "element_highlight_synchronization_verified":False})
    return {"schema_version":1,"video_count":len(rows),"videos":rows,
            "all_videos_under_600_seconds":all(x["technical_duration_pass"] for x in rows),
            "highlight_sync_verified":False,
            "academic_content_verified":False,
            "videos_modified":False,
            "publication_performed":False}
def main(argv=None):
    parser=argparse.ArgumentParser(description="Nonpublishing read-only MP4 duration checks")
    parser.add_argument("videos",type=Path,nargs="+")
    args=parser.parse_args(argv)
    result=audit_videos(args.videos)
    print(json.dumps(result,indent=2))
    return 0 if result["all_videos_under_600_seconds"] else 2
if __name__=="__main__":raise SystemExit(main())
