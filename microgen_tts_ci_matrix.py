"""Validate a GitHub Actions four-job matrix snapshot without claiming its origin."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
EXPECTED={f"unit ({os}, {py})" for os in ("windows-latest","ubuntu-latest") for py in ("3.11","3.12")}
class MatrixAuditError(ValueError):pass

def validate_ci_matrix(jobs:list[dict])->dict:
    if not isinstance(jobs,list) or len(jobs)!=4:
        raise MatrixAuditError("Expected exactly four independent matrix jobs")
    seen=set();blocking=[]
    for job in jobs:
        if not isinstance(job,dict) or not isinstance(job.get("name"),str):
            raise MatrixAuditError("Malformed workflow job")
        name=job["name"]
        if name not in EXPECTED or name in seen:
            raise MatrixAuditError("Missing, repeated, or unknown CI matrix job")
        seen.add(name)
        if job.get("status")!="completed" or job.get("conclusion")!="success":
            blocking.append(name)
        if not isinstance(job.get("id"),int) or job["id"]<=0:
            raise MatrixAuditError("Missing concrete workflow job ID")
    return {"schema_version":1,"matrix_complete":seen==EXPECTED,
        "all_jobs_passed":not blocking,"blocking_job_names":sorted(blocking),
        "job_ids":sorted(job["id"] for job in jobs),
        "ci_snapshot_validated_structurally":True,
        "github_api_origin_authenticated_by_this_function":False,
        "publication_performed":False}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("github_jobs_json",type=Path)
    args=p.parse_args(argv)
    payload=json.loads(args.github_jobs_json.read_text(encoding="utf8"))
    result=validate_ci_matrix(payload["jobs"])
    print(json.dumps(result,indent=2))
    return 0 if result["all_jobs_passed"] else 2
if __name__=="__main__":raise SystemExit(main())
