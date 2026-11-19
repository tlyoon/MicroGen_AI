"""Safe normal-batch checkpoint migration after accepted timed cue repair.

A real independent acoustic pass may finish before the outer runner records
its stage. If post-stage TTS reuse verification rejected a genuine one-cue
change, migrate ONLY a narrowly attested verifier-only code revision.
Never replay Gemini/TTS or broadly rekey scientific checkpoints.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable


class PostAcousticResumeError(RuntimeError):
    pass


# Adding this reconciliation must NOT silently approve scientific reviewers,
# speech prompts, source renderers, voices, math policy or video generators.
ALLOWED_RECONCILIATION_CODE_DELTA=frozenset({
    "microgen_batch.py",
    "microgen_campaign_authorization.py",
    "microgen_post_acoustic_reuse_resume.py",
    "microgen_verified_tts_reuse.py",
    "microgen_verified_upstream_reuse.py",
    "microgen_recovery_registry_v6.json",
    "docs/RELEASE_CLOSURE_DEVELOPMENT_CONTRACT_20261107.md",
    "docs/SOURCE_OPERATOR_SINGLE_CUE_RECOVERY_20261118.md",
    "tests/test_microgen_source_operator_cue_recovery.py",
    "tests/test_microgen_post_acoustic_reuse_resume.py",
})



def verify_original_authorization_module_delta(
    stage:Path, original_sha256:str, *, git_runner:Callable|None=None,
) -> dict:
    """Verify the *exact* historic TTS producer and narrow code-only change.

    The owner grant, source and real Git history—not a newly written TTS
    receipt—attest why the authorization module changed after synthesis.
    No synthesis/media policy is whitelisted; no money can be spent here.
    """
    import hashlib
    import json
    import os
    import socket

    stage=Path(stage)
    name="microgen_campaign_authorization.py"
    if (not isinstance(original_sha256,str)
            or not re.fullmatch("[0-9a-f]{64}",original_sha256)
            or stage.is_symlink() or not stage.is_dir()):
        raise PostAcousticResumeError("Untrusted TTS authorization SHA")
    grant_file=stage.parent/".microgen_bounded_provider_authorization.json"
    cp_file=stage/".microgen_checkpoint.json"
    if (not grant_file.is_file() or grant_file.is_symlink()
            or not cp_file.is_file() or cp_file.is_symlink()):
        raise PostAcousticResumeError("Missing immutable original grant/checkpoint")
    try:
        grant=json.loads(grant_file.read_text(encoding="utf8"))
        cp=json.loads(cp_file.read_text(encoding="utf8"))
    except (OSError,UnicodeError,ValueError) as exc:
        raise PostAcousticResumeError("Untrusted original provider grant") from exc
    if not isinstance(grant,dict) or not isinstance(cp,dict):
        raise PostAcousticResumeError("Invalid historical authorization shape")
    scope=grant.get("scope")
    if not isinstance(scope,dict):
        raise PostAcousticResumeError("Missing owner scope")
    old=scope.get("code_revision")
    repo=Path(scope.get("repo","/invalid"))
    current=repo/name
    staged=stage/name
    failed=cp.get("last_error")
    accepted=cp.get("post_acoustic_reconciliation")
    has_old_failure=(isinstance(failed,dict)
                     and failed.get("stage")=="acoustic_qa"
                     and failed.get("type")=="VerifiedTTSReuseError"
                     and failed.get("message")==
                       "Recovered WAV or cache integrity drift"
                     and isinstance(cp.get("inflight_provider_stage"),dict)
                     and cp["inflight_provider_stage"].get("stage")=="acoustic_qa")
    has_reconciled=(isinstance(accepted,dict)
                    and accepted.get("status")==
                       "SOURCE_BOUND_ONE_CUE_AUDIO_CHECKPOINT_RECONCILED"
                    and accepted.get("new_paid_requests") is False)
    if (grant.get("schema_version")!=1
            or grant.get("publication_authorized") is not False
            or not isinstance(old,str) or not re.fullmatch("[0-9a-f]{40}",old)
            or scope.get("host")!=socket.gethostname().casefold()
            or scope.get("host")!="hp"
            or Path(scope.get("work_root","/invalid")).resolve()!=stage.parent.resolve()
            or Path(scope.get("source","/invalid")).parent.name!=stage.name
            or scope.get("stop_after")!="acceptance"
            or scope.get("source_sha256")!=_file_sha(stage/"source.pdf")
            or not staged.is_file() or staged.is_symlink()
            or not current.is_file() or current.is_symlink()
            or not(has_old_failure or has_reconciled)):
        raise PostAcousticResumeError("Provider scope or audio checkpoint drift")
    head=_head_git(repo,git_runner)
    intermediate=cp.get("package_commit")
    if not isinstance(intermediate,str) or not re.fullmatch(
            "[0-9a-f]{40}",intermediate):
        raise PostAcousticResumeError("Unrecognized checkpoint revision")
    if git_runner is None:
        for earlier,later in ((old,intermediate),(intermediate,head)):
            ancestry=subprocess.run(
                ["git","merge-base","--is-ancestor",earlier,later],
                cwd=repo,capture_output=True,timeout=20)
            if ancestry.returncode!=0:
                raise PostAcousticResumeError(
                    "Historical checkpoint is outside verified Git ancestry")
        original_staged=subprocess.run(
            ["git","show",intermediate+":"+name],cwd=repo,
            capture_output=True,timeout=20,check=True).stdout
        if original_staged!=staged.read_bytes():
            raise PostAcousticResumeError(
                "Staged authorization code differs from its pinned commit")
    elif intermediate not in (old,head):
        raise PostAcousticResumeError(
            "Injected tests must pin original or current revision")
    if head==old:
        raise PostAcousticResumeError("No new verified audio recovery code")
    if git_runner is None:
        status=subprocess.run(["git","status","--porcelain"],cwd=repo,
                              capture_output=True,text=True,timeout=20,check=True)
        if status.stdout.strip():
            raise PostAcousticResumeError("Uncommitted code not trusted")
        historical=subprocess.run(["git","show",old+":"+name],cwd=repo,
                                  capture_output=True,timeout=20,check=True).stdout
        modified=subprocess.run(
            ["git","diff","--name-only",old,head,"--"],cwd=repo,
            capture_output=True,text=True,timeout=20,check=True).stdout.splitlines()
    else:
        historical,modified=git_runner(old,head,name)
    if (hashlib.sha256(historical).hexdigest()!=original_sha256
            or not isinstance(modified,list)
            or len(modified)!=len(set(modified))
            or not set(modified)<=ALLOWED_RECONCILIATION_CODE_DELTA
            or not {"microgen_campaign_authorization.py",
                    "microgen_verified_tts_reuse.py",
                    "microgen_batch.py"}<=set(modified)):
        raise PostAcousticResumeError("TTS producer code revision not source attested")
    return {"old_commit":old,"current_commit":head,
            "historical_authorization_sha256":original_sha256,
            "changed_code":sorted(modified),
            "no_provider_scope_inherited":True}


def _file_sha(path:Path)->str:
    import hashlib
    with Path(path).open("rb") as inp:
        return hashlib.file_digest(inp,"sha256").hexdigest()


def _head_git(repo:Path,git_runner:Callable|None)->str:
    if git_runner is not None:
        return subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,
                                       text=True,timeout=20).strip()
    out=subprocess.run(["git","rev-parse","HEAD"],cwd=repo,
                       capture_output=True,text=True,timeout=20,check=True)
    head=out.stdout.strip()
    if not re.fullmatch("[0-9a-f]{40}",head):
        raise PostAcousticResumeError("Git HEAD not trustworthy")
    return head

def reconcile_verified_audio_receipt(
    repo:Path,stage:Path,cp:dict,prior_commit:str,current_commit:str,
    stage_valid:Callable,dependency_fingerprint:Callable,dest:Path,
    *,
    git_diff:Callable|None=None,
)->dict|None:
    """Rekey verified science/TTS/acoustic stages, never their media or grants.

    Return new fingerprint values only after EVERY source/policy/QA check
    succeeds; caller then atomically marks acoustic_qa complete and persists
    the checkpoint through normal batch's existing save mechanism.
    """
    pending=cp.get("inflight_provider_stage")
    error=cp.get("last_error")
    if (not isinstance(pending,dict)
            or pending.get("stage")!="acoustic_qa"
            or not isinstance(error,dict)
            or error.get("stage")!="acoustic_qa"
            or error.get("type")!="VerifiedTTSReuseError"
            or error.get("message")!="Recovered WAV or cache integrity drift"):
        return None
    if (not isinstance(prior_commit,str)
            or not re.fullmatch(r"[0-9a-f]{40}",prior_commit)
            or not isinstance(current_commit,str)
            or not re.fullmatch(r"[0-9a-f]{40}",current_commit)
            or prior_commit==current_commit):
        raise PostAcousticResumeError(
            "No separately pinned tested verifier revision to reconcile")
    repo,stage=Path(repo),Path(stage)
    if git_diff is None:
        process=subprocess.run(
            ["git","diff","--name-only",prior_commit,current_commit,"--"],
            cwd=repo,capture_output=True,text=True,timeout=20,check=True)
        files=[line.strip().replace("\\","/") for line in
               process.stdout.splitlines() if line.strip()]
    else:
        files=git_diff(prior_commit,current_commit)
    if (not isinstance(files,list) or not files or
            len(files)!=len(set(files))
            or not set(files)<=ALLOWED_RECONCILIATION_CODE_DELTA
            or not {"microgen_verified_tts_reuse.py",
                    "microgen_batch.py"}<=set(files)):
        raise PostAcousticResumeError(
            "Source/science/voice/producer changed: no checkpoint migration")
    from microgen_verified_tts_reuse import verify_reuse_receipt
    reused=verify_reuse_receipt(stage)
    if (not isinstance(reused,dict)
            or reused.get("status")!=
            "SOURCE_BOUND_PCM_RECONCILED_WITH_ACCEPTED_ONE_CUE_REPAIR"):
        raise PostAcousticResumeError(
            "Authenticated acoustic repair and TTS reuse not reconciled")
    if (not all(cp.get("completed",{}).get(name)
                for name in ("science_qa","tts","acoustic_qa"))):
        raise PostAcousticResumeError("Original verified stages are incomplete")
    # Full three-stage verification is performed BEFORE any fingerprint is
    # modified. A test stub must prove the same operations and no provider.
    checks={}
    for name in ("science_qa","tts","acoustic_qa"):
        if stage_valid(stage,name,dest) is not True:
            raise PostAcousticResumeError(
                "Stale source-grounded prior stage: "+name)
        value=dependency_fingerprint(stage,name)
        if not isinstance(value,str) or not re.fullmatch(r"[0-9a-f]{64}",value):
            raise PostAcousticResumeError("Untrusted stage fingerprint")
        checks[name]=value
    return {
        "status":"SOURCE_BOUND_ONE_CUE_AUDIO_CHECKPOINT_RECONCILED",
        "previous_commit":prior_commit,
        "verified_commit":current_commit,
        "verified_changed_code":sorted(files),
        "fingerprints":checks,
        "source_accepted_reuse_receipt_sha256":reused["receipt_sha256"],
        "independent_acoustic_receipt_sha256":
            reused["acoustic_receipt_sha256"],
        "new_paid_requests":False,
        "publication_allowed":False,
    }
