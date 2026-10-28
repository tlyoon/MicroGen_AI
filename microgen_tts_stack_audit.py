"""Read-only first-parent ancestry audit for an isolated local draft stack."""
from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path

class StackAuditError(ValueError):pass
def _git(repo:Path,*args)->str:
    p=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,timeout=20)
    if p.returncode:raise StackAuditError("Cannot verify git "+args[0]+": "+p.stderr[:300])
    return p.stdout.strip()

def audit_stack(repo:Path,base:str,head:str,*,max_commits:int=100)->dict:
    repo=Path(repo).resolve(strict=True)
    if type(max_commits)!=int or not 1<=max_commits<=500:
        raise StackAuditError("Invalid bounded commit budget")
    if _git(repo,"status","--porcelain"):
        raise StackAuditError("Dirty checkout cannot serve as reviewed stack evidence")
    for rev in (base,head):_git(repo,"rev-parse","--verify",rev+"^{commit}")
    if _git(repo,"merge-base",base,head)!=_git(repo,"rev-parse",base):
        raise StackAuditError("Draft stack base is not an ancestor of head")
    parents=_git(repo,"rev-list","--parents","--reverse",f"{base}..{head}")
    lines=[line.split() for line in parents.splitlines() if line.strip()]
    if not lines or len(lines)>max_commits:
        raise StackAuditError("Empty or unbounded draft commit range")
    if any(len(tokens)!=2 for tokens in lines):
        raise StackAuditError("Merge commits found: stacked PRs require linear history")
    previous=_git(repo,"rev-parse",base)
    for commit,parent in lines:
        if parent!=previous:raise StackAuditError("Disconnected first-parent history")
        previous=commit
    if previous!=_git(repo,"rev-parse",head):
        raise StackAuditError("Head does not end first-parent chain")
    return {"schema_version":1,"status":"LINEAR_DRAFT_ANCESTRY_VERIFIED",
      "base_sha256":_git(repo,"rev-parse",base),"head_sha256":previous,
      "commit_count":len(lines),"commit_sha256":[x[0] for x in lines],
      "git_history_modified":False,"production_merge_performed":False,
      "ci_pass_verified":False,"academic_review_verified":False}

def main(argv=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("checkout",type=Path);parser.add_argument("base_commit")
    parser.add_argument("head_commit");parser.add_argument("--max-commits",type=int,default=100)
    args=parser.parse_args(argv)
    print(json.dumps(audit_stack(args.checkout,args.base_commit,args.head_commit,
                                  max_commits=args.max_commits),indent=2))
    return 0
if __name__=="__main__":raise SystemExit(main())
