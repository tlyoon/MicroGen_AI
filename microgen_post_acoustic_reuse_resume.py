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
    "microgen_post_acoustic_reuse_resume.py",
    "microgen_verified_tts_reuse.py",
    "microgen_recovery_registry_v6.json",
    "docs/RELEASE_CLOSURE_DEVELOPMENT_CONTRACT_20261107.md",
    "docs/SOURCE_OPERATOR_SINGLE_CUE_RECOVERY_20261118.md",
    "tests/test_microgen_source_operator_cue_recovery.py",
    "tests/test_microgen_post_acoustic_reuse_resume.py",
})


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
