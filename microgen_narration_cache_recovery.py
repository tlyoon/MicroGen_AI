"""Source- and request-hash-verified reuse of completed Gemini narration batches.

A failed whole-lecture stage may contain fully validated, atomically written
narration batches. Reusing those exact responses avoids repeat paid requests
when a later code revision repairs a deterministic local TTS-only blocker.
No failed stage or original provider authorization is imported or renewed.
The normal narration runner independently recomputes the complete source,
slides, model and composed-prompt key before accepting ANY copied response.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket

CACHE_NAME = re.compile(r"batch_\d{4}\.json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
MAX_CAMPAIGNS = 400
MAX_CACHED_BATCHES = 16
MAX_JSON_BYTES = 65536


def _sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _json(path: Path):
    if (path.is_symlink() or not path.is_file() or
            not 0 < path.stat().st_size <= MAX_JSON_BYTES):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _scope(stage: Path, source_sha: str):
    permit = _json(stage.parent / ".microgen_bounded_provider_authorization.json")
    cp = _json(stage / ".microgen_checkpoint.json")
    src = stage / "source.pdf"
    if (not permit or not cp or src.is_symlink() or not src.is_file()
            or _sha(src) != source_sha
            or permit.get("publication_authorized") is not False):
        return False
    s = permit.get("scope", {})
    return bool(
        isinstance(s, dict)
        and s.get("host") == "hp"
        and s.get("stop_after") == "acceptance"
        and s.get("source_sha256") == source_sha
        and SHA.fullmatch(str(s.get("code_revision", "")))
        and cp.get("package_commit") == s.get("code_revision")
    )


def reuse_verified_narration_batches(stage: Path, *,
                                      checkpoint_root: Path | None = None,
                                      require_hp: bool = True) -> dict:
    """Copy verified historical response records for re-hashing by the runner.

    Safe under interrupted/terminal historical stage: it transfers neither
    checkpoint status nor paid usage grant. Unsupported scopes abstain.
    """
    if require_hp and (os.name != "nt" or socket.gethostname().lower() != "hp"):
        return {"status": "WRONG_HOST_ABSTAINED", "copied": 0}
    stage = Path(stage).resolve()
    root = (Path(checkpoint_root) if checkpoint_root is not None
            else Path(os.environ.get("LOCALAPPDATA", "/unavailable"))
                 / "MicroGen_AI_Checkpoints").resolve()
    if (not stage.is_dir() or stage.is_symlink()
            or stage.parent.parent != root):
        return {"status": "OUT_OF_SCOPE_ABSTAINED", "copied": 0}
    src = stage / "source.pdf"
    if src.is_symlink() or not src.is_file():
        return {"status": "SOURCE_UNAVAILABLE", "copied": 0}
    source_sha = _sha(src)
    if not _scope(stage, source_sha):
        return {"status": "CURRENT_CAMPAIGN_UNVERIFIED", "copied": 0}
    campaigns = sorted(
        (p for p in root.iterdir() if p.is_dir() and not p.is_symlink()),
        key=lambda x: x.name, reverse=True,
    )
    if len(campaigns) > MAX_CAMPAIGNS:
        return {"status": "CAMPAIGN_SCAN_LIMIT", "copied": 0}
    target = stage / ".microgen_narration_batches"
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise RuntimeError("Unsafe narration cache destination")
    if not target.exists():
        target.mkdir()
    imported = 0
    for parent in campaigns:
        if parent == stage.parent:
            continue
        old = parent / stage.name
        cache = old / ".microgen_narration_batches"
        if (not old.is_dir() or old.is_symlink()
                or not _scope(old, source_sha)
                or not cache.is_dir() or cache.is_symlink()):
            continue
        candidates = sorted(cache.iterdir(), key=lambda x: x.name)
        if len(candidates) > MAX_CACHED_BATCHES:
            continue
        for candidate in candidates:
            if not CACHE_NAME.fullmatch(candidate.name):
                continue
            data = _json(candidate)
            if (not data or not SHA.fullmatch(str(data.get("key", "")))
                    or not isinstance(data.get("narration"), dict)
                    or not 1 <= len(data["narration"]) <= 20
                    or any(not isinstance(x, str) or not x for x in
                           data["narration"])):
                continue
            destination = target / candidate.name
            if destination.exists() or destination.is_symlink():
                # Never replace current/earlier accepted responses.
                continue
            if _json(candidate) != data or _sha(old / "source.pdf") != source_sha:
                raise RuntimeError("Historical narration record changed")
            with destination.open("xb") as output:
                output.write(candidate.read_bytes())
            imported += 1
        if imported:
            break  # single previous trusted campaign, no multi-source mixing
    return {
        "status": ("COPIED_REQUIRES_CURRENT_REQUEST_REHASH"
                   if imported else "NO_ELIGIBLE_CACHED_BATCHES"),
        "copied": imported,
    }
