"""Reuse only source- and request-hash-verifiable Gemini figure mapping replies.

This is an acceleration mechanism, NOT a substitute for figure mapping QA.
The current mapper independently re-hashes the exact model/prompt/page/crops
before accepting a copied response. Failed prior stage receipts are NEVER
imported or marked successful. Never re-request a previously proven identical
Gemini call merely because the *code* learned a new source-PDF recovery rule.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket

CACHE_NAME = re.compile(r"page_[1-9]\d*_(?:captions|mapping_\d{4})\.json\Z")
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_RECORDS=80
MAX_BYTES=32768
MAX_SCAN_DIRS=400


def _sha(path:Path)->str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def _safe_json(path:Path,max_bytes:int=MAX_BYTES):
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= max_bytes):
        return None
    try:
        data=json.loads(path.read_text(encoding="utf8"))
    except (UnicodeError,ValueError,OSError):
        return None
    return data if isinstance(data,dict) else None


def reuse_verified_mapping_cache(stage: Path, *, checkpoint_root:Path|None=None,
                                 require_hp:bool=True) -> dict:
    """Import only bounded completed hash-keyed captions/figure responses.

    Source/campaign/code identity is independently attested before import.
    Current _cached_figure_request re-computes its key, preventing any
    old, edited, or model-incompatible response from being *used*.
    """
    if require_hp and (os.name!="nt" or socket.gethostname().lower()!="hp"):
        return {"responses_copied":0,"status":"WRONG_HOST_ABSTAINED"}
    stage=Path(stage).resolve()
    root=(Path(checkpoint_root) if checkpoint_root is not None
          else Path(os.environ.get("LOCALAPPDATA","/unavailable"))/
                "MicroGen_AI_Checkpoints").resolve()
    if (not stage.is_dir() or stage.is_symlink()
            or stage.parent.parent!=root):
        return {"responses_copied":0,"status":"OUT_OF_SCOPE_ABSTAINED"}
    source=stage/"source.pdf"
    if source.is_symlink() or not source.is_file():
        return {"responses_copied":0,"status":"UNVERIFIED_SOURCE_ABSTAINED"}
    source_sha=_sha(source)
    current_grant=_safe_json(stage.parent/".microgen_bounded_provider_authorization.json")
    current_cp=_safe_json(stage/".microgen_checkpoint.json")
    if (not current_grant or not current_cp
            or current_grant.get("publication_authorized") is not False
            or current_grant.get("scope",{}).get("host")!="hp"
            or current_grant.get("scope",{}).get("stop_after")!="acceptance"
            or current_grant["scope"].get("source_sha256")!=source_sha
            or current_cp.get("package_commit")!=current_grant["scope"].get("code_revision")):
        return {"responses_copied":0,"status":"UNVERIFIED_CAMPAIGN_ABSTAINED"}
    eligible=[]
    children=sorted(root.iterdir(),key=lambda p:p.name)
    if len(children)>MAX_SCAN_DIRS:
        return {"responses_copied":0,"status":"TOO_MANY_CAMPAIGNS_ABSTAINED"}
    for parent in children:
        if (parent==stage.parent or parent.is_symlink() or not parent.is_dir()):
            continue
        old=parent/stage.name
        permit=_safe_json(parent/".microgen_bounded_provider_authorization.json")
        cp=_safe_json(old/".microgen_checkpoint.json")
        if (not old.is_dir() or old.is_symlink()
                or not permit or not cp
                or permit.get("publication_authorized") is not False
                or permit.get("scope",{}).get("host")!="hp"
                or permit.get("scope",{}).get("stop_after")!="acceptance"
                or permit["scope"].get("source_sha256")!=source_sha
                or cp.get("package_commit")!=permit["scope"].get("code_revision")):
            continue
        old_src=old/"source.pdf"
        cachedir=old/".microgen_mapping_cache"
        if (old_src.is_symlink() or not old_src.is_file()
                or _sha(old_src)!=source_sha
                or cachedir.is_symlink() or not cachedir.is_dir()):
            continue
        candidates=sorted(cachedir.glob("*.json"))
        if len(candidates)>MAX_RECORDS:
            continue
        entries=[]
        for candidate in candidates:
            if not CACHE_NAME.fullmatch(candidate.name):
                continue
            rec=_safe_json(candidate)
            if (not rec or not HEXDIGEST.fullmatch(str(rec.get("key","")))
                    or not isinstance(rec.get("response"),str)
                    or not 1 <= len(rec["response"]) <= 16000):
                continue
            entries.append((candidate.name,candidate,rec))
        if entries:
            eligible.append((str(parent.name),entries))
    if not eligible:
        return {"responses_copied":0,"status":"NO_VERIFIED_PREVIOUS_RESPONSES"}
    # Prefer newest scoped campaign. A same cache filename with different key
    # cannot be copied twice. Current mapping re-verifies its complete key.
    eligible.sort(reverse=True)
    selected={}
    for _,entries in eligible:
        for name,path,rec in entries:
            selected.setdefault(name,(path,rec))
    target=stage/".microgen_mapping_cache"
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError("Unsafe destination for verified model response cache")
        # Avoid consuming or overwriting an existing cache at all.
        if any(target.iterdir()):
            return {"responses_copied":0,"status":"CURRENT_MAPPING_CACHE_ALREADY_PRESENT"}
    else:
        target.mkdir()
    written=[]
    try:
        for name,(src,rec) in sorted(selected.items()):
            # External drift between selection and copy must fail closed.
            if _safe_json(src)!=rec:
                raise RuntimeError("Historical Gemini response changed during copy")
            dst=target/name
            with dst.open("xb") as stream:
                written.append(dst)
                stream.write(src.read_bytes())
        if _sha(source)!=source_sha:
            raise RuntimeError("Current source changed during cache import")
    except Exception:
        for dest in written:
            dest.unlink(missing_ok=True)
        raise
    return {"responses_copied":len(written),
            "status":"SOURCE_BOUND_REPLIES_COPIED_REQUIRE_CURRENT_PROMPT_REHASH"}
