"""Automatically reuse ONLY previously verified source-identical TTS PCM.

This is a *production* pre-TTS recovery for a new, separately authorized HP
private campaign when only downstream acoustic review code has changed.
Never import prior acoustic verdicts, publisher rights, or old paid grants.

A change to narration, the reviewed mathematical voice rules, the source
PDF, timed cue plan, TTS implementation, or synthesizer settings prevents
reuse and requires the ordinary finite paid TTS workflow. The independent
acoustic gate ALWAYS re-runs on the immutable reused WAVs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import tempfile

RECEIPT = ".microgen_verified_audio_reuse.json"
OWNER = ".microgen_bounded_provider_authorization.json"
# Exact producer dependencies, not acoustic comparator dependencies.
PRODUCER = (
    "text_to_speech_v25.py", "microgen_flash_tts.py",
    "microgen_timed_cue_tts.py", "microgen_timed_cue_planner.py",
    "microgen_cue_semantic_mapping.py", "microgen_timed_highlight_contract.py",
    "microgen_reviewed_math_voice.py", "microgen_tts_provenance.py",
    "microgen_private_dev_policy.py", "microgen_campaign_authorization.py",
)
SOURCE = ("source.pdf", "slides.pdf", "script_tts.json", "script.txt")
TIMED = (".microgen_timed_cue_plan.json",
         ".microgen_timed_highlights.json",
         ".microgen_tts_provenance.json")
DIRS = ("highlight_chunks", ".microgen_tts_cache")
MAX_FILES = 300
MAX_BYTES = 500_000_000


class VerifiedTTSReuseError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _read(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128_000:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except (ValueError, UnicodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _same_inputs(old: Path, stage: Path) -> bool:
    # Exact source/producer identity: no PDF-specific tolerance, no script
    # similarity, and no code-only whitelist that might hide an audio change.
    return all(
        (old / name).is_file() and (stage / name).is_file()
        and not (old / name).is_symlink()
        and not (stage / name).is_symlink()
        and _sha(old / name) == _sha(stage / name)
        for name in SOURCE + PRODUCER
    )


def _inventory(old: Path, count: int) -> tuple[list[str], dict[str,str]]:
    files = list(TIMED[1:]) + [f"slide{i}.wav" for i in range(1,count+1)]
    if any(not (old / n).is_file() or (old / n).is_symlink() for n in files):
        raise VerifiedTTSReuseError("Missing or linked source TTS PCM/receipt")
    manifest={}
    length=0
    for name in files:
        path=old/name
        manifest[name]=_sha(path)
        length+=path.stat().st_size
    for dirname in DIRS:
        folder=old/dirname
        if folder.is_symlink() or not folder.is_dir():
            raise VerifiedTTSReuseError("Untrusted chunk/cache directory")
        for child in sorted(folder.rglob("*")):
            if child.is_symlink() or not child.is_file():
                raise VerifiedTTSReuseError("Nested or linked audio asset")
            rel=child.relative_to(old).as_posix()
            if dirname=="highlight_chunks":
                if not re.fullmatch(r"highlight_chunks/slide[1-9]\d*_cue[1-9]\d*\.wav",rel):
                    raise VerifiedTTSReuseError("Unexpected highlight filename")
            elif not re.fullmatch(
                    r"\.microgen_tts_cache/(?:slide[1-9]\d*|"
                    r"pronunciation-risk-[0-9a-f]{24}|"
                    r"pronunciation_evidence_[0-9a-f]{20})\.json",rel):
                raise VerifiedTTSReuseError("Unexpected cache filename")
            manifest[rel]=_sha(child)
            length+=child.stat().st_size
            if len(manifest)>MAX_FILES or length>MAX_BYTES:
                raise VerifiedTTSReuseError("Prior audio inventory exceeds bound")
    return files,manifest


def _verify(stage: Path, count: int) -> None:
    from microgen_autonomous_acoustic_gate import _normalized
    from microgen_tts_provenance import verify_manifest
    from microgen_timed_highlight_contract import inspect_timed_highlights
    from microgen_quality import check_wavs
    texts=_normalized(stage)
    if len(texts)!=count:
        raise VerifiedTTSReuseError("Original script slide count drift")
    from microgen_timed_cue_tts import _verified_plan
    from microgen_reviewed_math_voice import preflight_voice_sidecar
    preflight_voice_sidecar(stage)
    _verified_plan(stage)
    verify_manifest(stage,texts)
    check_wavs(stage,count)
    info=inspect_timed_highlights(stage)
    if not info or info.get("slide_count",count)!=count:
        raise VerifiedTTSReuseError("Incorrect timed source cue inventory")


def maybe_reuse_verified_tts(stage: Path, *, work_root: Path, source_sha: str,
                             mark_complete, cp: dict, checkpoint_path: Path,
                             stage_valid, dest: Path) -> dict | None:
    """Recover valid TTS at the real normal stage boundary, not acoustic pass.

    No changes are made unless the local authorized source+producer identity
    and ALL PCM/timed-provenance prechecks pass. One bounded, reversible copy.
    """
    stage=Path(stage)
    work_root=Path(work_root)
    root=work_root.parent
    if (os.name!="nt" or socket.gethostname().casefold()!="hp"
            or stage.parent != work_root
            or root != Path(os.environ.get("LOCALAPPDATA","/unavailable")) /
               "MicroGen_AI_Checkpoints"):
        return None
    new_grant=_read(work_root/OWNER)
    if (new_grant is None or new_grant.get("publication_authorized") is not False
            or new_grant.get("scope",{}).get("host")!="hp"
            or new_grant.get("scope",{}).get("source_sha256")!=source_sha
            or new_grant.get("scope",{}).get("stop_after")!="acceptance"
            or new_grant.get("scope",{}).get("code_revision") !=
               cp.get("package_commit")
            or not (stage/"source.pdf").is_file()
            or _sha(stage/"source.pdf")!=source_sha):
        return None
    if not all(cp.get("completed",{}).get(name) for name in (
            "figure_extraction","figure_mapping","figure_merge",
            "slides","narration","science_qa")):
        return None
    if any((stage / name).exists() or (stage / name).is_symlink()
           for name in TIMED[1:] + DIRS) or list(stage.glob("slide*.wav")):
        return None
    if (stage/RECEIPT).exists():
        raise VerifiedTTSReuseError("Old local audio-reuse receipt present")
    from microgen_quality import check_slide_pdf
    count=check_slide_pdf(stage/"slides.pdf",require_footer=True)["pages"]
    entries=[]
    for previous in root.iterdir():
        if (previous==work_root or previous.is_symlink()
                or not previous.is_dir()):
            continue
        grant=_read(previous/OWNER)
        if (grant is None or grant.get("publication_authorized") is not False
                or grant.get("scope",{}).get("host")!="hp"
                or grant.get("scope",{}).get("source_sha256")!=source_sha
                or grant.get("scope",{}).get("stop_after")!="acceptance"):
            continue
        # Only acoustic reviewer identities may change. A voice/provider,
        # output format, cue budget or synthesis setting change makes the
        # old WAVs ineligible even if all source text is identical.
        new_environment=new_grant.get("scope",{}).get("provider_environment")
        old_environment=grant.get("scope",{}).get("provider_environment")
        if not isinstance(new_environment,dict) or not isinstance(old_environment,dict):
            continue
        voice_scope=lambda value: {
            key: setting for key,setting in value.items()
            if key not in {"MICROGEN_ACOUSTIC_MODEL_A",
                           "MICROGEN_ACOUSTIC_MODEL_B"}}
        if voice_scope(new_environment)!=voice_scope(old_environment):
            continue
        old=previous/stage.name
        old_cp=_read(old/".microgen_checkpoint.json")
        if (old_cp is None
                or old_cp.get("package_commit")!=grant.get("scope",{}).get("code_revision")
                or not old_cp.get("completed",{}).get("tts")):
            continue
        try:
            if not _same_inputs(old,stage):
                continue
            old_plan=old/TIMED[0]
            current_plan=stage/TIMED[0]
            if (old_plan.is_symlink() or not old_plan.is_file()
                    or current_plan.is_symlink()
                    or (current_plan.exists() and
                        _sha(old_plan)!=_sha(current_plan))):
                continue
            if any(not (old/f"slide{i}.pdf").is_file()
                   or not (stage/f"slide{i}.pdf").is_file()
                   or (old/f"slide{i}.pdf").is_symlink()
                   or (stage/f"slide{i}.pdf").is_symlink()
                   or _sha(old/f"slide{i}.pdf") != _sha(stage/f"slide{i}.pdf")
                   for i in range(1,count+1)):
                continue
            _verify(old,count)
            _,manifest=_inventory(old,count)
            entries.append((str(old_cp["completed"]["tts"]),
                            old,manifest))
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            continue
    if not entries:
        return None
    entries.sort(key=lambda e:e[0],reverse=True)
    if len(entries)>1 and entries[0][0]==entries[1][0]:
        raise VerifiedTTSReuseError("Ambiguous equally recent TTS checkpoint")
    _,old,manifest=entries[0]
    # Verify in a wholly new candidate directory before touching stage.
    with tempfile.TemporaryDirectory(prefix=".microgen-audio-reuse-",
                                     dir=work_root) as tmp:
        candidate=Path(tmp)
        for name in SOURCE:
            shutil.copy2(stage/name,candidate/name)
        plan_source=(stage/TIMED[0] if (stage/TIMED[0]).is_file()
                     else old/TIMED[0])
        shutil.copy2(plan_source,candidate/TIMED[0])
        for i in range(1,count+1):
            shutil.copy2(stage/f"slide{i}.pdf",
                         candidate/f"slide{i}.pdf")
        for name in manifest:
            path=candidate/name
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(old/name,path)
            if _sha(path)!=manifest[name]:
                raise VerifiedTTSReuseError("Audio copy hash drift")
        _verify(candidate,count)
        # No earlier acoustic decision, failed report or provider grant copied.
        transferred=[]
        try:
            if not (stage/TIMED[0]).exists():
                shutil.copy2(candidate/TIMED[0],stage/TIMED[0])
                transferred.append(stage/TIMED[0])
            for name in manifest:
                dest_path=stage/name
                if dest_path.exists() or dest_path.is_symlink():
                    raise VerifiedTTSReuseError("Concurrent audio destination")
                dest_path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(candidate/name,dest_path)
                transferred.append(dest_path)
            _verify(stage,count)
            receipt={
                "schema_version":1,
                "status":"SOURCE_BOUND_PCM_REVERIFIED_ACOUSTIC_REVIEW_REQUIRED",
                "source_sha256":source_sha,
                "origin_campaign":old.parent.name,
                "cue_plan_sha256":_sha(stage/TIMED[0]),
                "tts_producer_sha256":{
                    name:_sha(stage/name) for name in PRODUCER},
                "file_sha256":manifest,
                "original_acoustic_approval_reused":False,
                "new_model_requests":False,
                "publication_allowed":False,
            }
            (stage/RECEIPT).write_text(
                json.dumps(receipt,indent=2,sort_keys=True),encoding="utf8")
            if not stage_valid(stage,"tts",dest):
                raise VerifiedTTSReuseError("New-code TTS stage recheck failed")
            mark_complete(cp,checkpoint_path,"tts",stage)
        except Exception:
            (stage/RECEIPT).unlink(missing_ok=True)
            for target in reversed(transferred):
                target.unlink(missing_ok=True)
            for dirname in DIRS:
                folder=stage/dirname
                if folder.exists() and not any(folder.rglob("*")):
                    folder.rmdir()
            raise
    return {"status":"SOURCE_BOUND_PCM_REVERIFIED_ACOUSTIC_REVIEW_REQUIRED",
            "from":old.parent.name,"wav_count":count,"new_model_requests":False,
            "old_acoustic_reused":False}


def verify_reuse_receipt(stage: Path) -> dict | None:
    """Bound future checkpoints to the originally copied source/voice/PCM."""
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.exists():
        return None
    receipt=_read(path)
    if (receipt is None or receipt.get("schema_version")!=1
            or receipt.get("status")!=
            "SOURCE_BOUND_PCM_REVERIFIED_ACOUSTIC_REVIEW_REQUIRED"
            or receipt.get("original_acoustic_approval_reused") is not False
            or receipt.get("new_model_requests") is not False
            or receipt.get("publication_allowed") is not False
            or receipt.get("source_sha256")!=_sha(stage/"source.pdf")
            or receipt.get("cue_plan_sha256")!=_sha(stage/TIMED[0])):
        raise VerifiedTTSReuseError("Untrusted previously recovered audio identity")
    code=receipt.get("tts_producer_sha256")
    if (not isinstance(code,dict) or set(code)!=set(PRODUCER)
            or any(_sha(stage/name)!=digest for name,digest in code.items())):
        raise VerifiedTTSReuseError("Recovered audio synthesis policy changed")
    files=receipt.get("file_sha256")
    if (not isinstance(files,dict) or len(files)>MAX_FILES
            or len(files)<4):
        raise VerifiedTTSReuseError("Recovered audio file inventory missing")
    for rel,digest in files.items():
        path=stage/rel
        if (not isinstance(rel,str) or not isinstance(digest,str)
                or not re.fullmatch(r"[0-9a-f]{64}",digest)
                or path.is_symlink() or not path.is_file()
                or stage.resolve() not in path.resolve().parents
                or _sha(path)!=digest):
            raise VerifiedTTSReuseError("Recovered WAV or cache integrity drift")
    return {"status":receipt["status"],"receipt_sha256":_sha(stage/RECEIPT)}
