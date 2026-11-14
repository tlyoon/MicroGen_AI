"""Durable, source-pinned authorization for a *single* bounded private campaign.

This avoids repeated operator approval on checkpoint resumes. Ordinary
single-source HP private G2/TTS development uses the owner's 12 Nov 2026
standing finite grant, with an exclusive source+Git-commit ledger. Other
campaigns still require the explicit --authorize-provider-usage flag.
No API call, publication permission, credential capture or retry reset occurs
in this module. Normal offline development never needs this receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess

RECEIPT = ".microgen_bounded_provider_authorization.json"
STATUS = "BOUNDED_PRIVATE_PROVIDER_SCOPE_AUTHORIZED"
ENVIRONMENT_KEYS = (
    "MICROGEN_FORMAL_TTS_PROVIDER",
    "MICROGEN_TTS_ENABLE_CLOUD_FALLBACK",
    "MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS",
    "MICROGEN_TTS_QUEUE_ROUNDS",
    "MICROGEN_TTS_VOICE",
    "MICROGEN_GEMINI_MAX_RETRIES",
    "MICROGEN_GEMINI_SDK_RETRY_ATTEMPTS",
    "MICROGEN_GEMINI_TRANSIENT_RETRIES_PER_KEY",
    "MICROGEN_TIMED_CUES",
    "MICROGEN_TIMED_SEMANTIC_ASSIST",
    "MICROGEN_TIMED_SEMANTIC_MAX_SLIDES",
    "MICROGEN_ACOUSTIC_MODEL_A",
    "MICROGEN_ACOUSTIC_MODEL_B",
)


class BoundedCampaignAuthorizationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BoundedCampaignAuthorizationError(message)


def _sha(path: Path) -> str:
    _require(path.is_file() and not path.is_symlink(),
             "Source PDF missing or unsafe; no provider authorization")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _revision(repo: Path) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=15,
        encoding="utf-8", errors="replace",
    )
    revision = process.stdout.strip()
    _require(process.returncode == 0 and bool(re.fullmatch(r"[0-9a-f]{40}", revision)),
             "Git revision not independently verifiable")
    return revision


def _identity(*, repo: Path, source_root: Path, work_root: Path,
              source_file: Path, stop_after: str, multipart: bool) -> dict:
    repo, source_root, work_root, source_file = (
        Path(p).resolve() for p in (repo, source_root, work_root, source_file)
    )
    _require(not work_root.is_relative_to(source_root)
             and not work_root.is_relative_to(repo),
             "Private campaign work root must be outside source and code folders")
    return {
        "repo": str(repo),
        "source_root": str(source_root),
        "work_root": str(work_root),
        "source": str(source_file),
        "source_sha256": _sha(source_file),
        "code_revision": _revision(repo),
        "host": socket.gethostname().casefold(),
        "stop_after": stop_after,
        "multipart": bool(multipart),
        "provider_environment": {k: os.environ.get(k, "") for k in ENVIRONMENT_KEYS},
    }


def authorize_or_resume(*, repo: Path, source_root: Path, work_root: Path,
                        source_file: Path, stop_after: str, stage_retries: int,
                        multipart: bool, explicit_authorization: bool,
                        standing_private_development: bool = False) -> dict:
    """Check one exact campaign; create only on an *explicitly* authorized launch.

    A later process may omit --authorize-provider-usage: it can use the same
    private source, Git head, stage ceiling, model settings and no *larger*
    per-stage retry budget. A different model, source, code or target stage
    must use a new independently authorized campaign; this function never
    enlarges an old consent.
    """
    root = Path(work_root).resolve()
    _require(os.name == "nt", "Bounded provider authorization is Windows-only")
    _require(isinstance(stop_after, str) and stop_after
             not in ("published", "figure_extraction"),
             "A bounded, unpublished provider stage is mandatory")
    _require(type(stage_retries) is int and 0 <= stage_retries <= 3,
             "Retry budget must be explicitly finite (0..3)")
    path = root / RECEIPT
    if path.exists() or path.is_symlink():
        _require(path.is_file() and not path.is_symlink(),
                 "Campaign authorization receipt is not a regular file")
    scope = _identity(
        repo=repo, source_root=source_root, work_root=root,
        source_file=source_file, stop_after=stop_after, multipart=multipart,
    )
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BoundedCampaignAuthorizationError(
                "Corrupt authorization receipt; no provider calls") from exc
        _require(type(existing) is dict and
                 set(existing) == {"schema_version", "status", "scope",
                                   "max_stage_retries", "publication_authorized"},
                 "Authorization receipt shape is untrusted")
        _require(existing["schema_version"] == 1
                 and existing["status"] == STATUS
                 and existing["publication_authorized"] is False,
                 "Authorization receipt does not grant private generation")
        _require(existing["scope"] == scope,
                 "Campaign source/code/stage/provider scope changed; stop before provider")
        cap = existing["max_stage_retries"]
        _require(type(cap) is int and 0 <= stage_retries <= cap <= 3,
                 "Cannot increase campaign retry budget on restart")
        # An observed terminal stage error already consumed an authorized
        # attempt. Without fresh causal evidence, a new process/session must
        # not replay that potentially metered operation under the same
        # campaign consent. The original runner still performs its bounded
        # within-process retries and key failover automatically.
        checkpoint = root / Path(source_file).parent.name / ".microgen_checkpoint.json"
        if checkpoint.exists() or checkpoint.is_symlink():
            _require(checkpoint.is_file() and not checkpoint.is_symlink(),
                     "Unsafe prior stage checkpoint")
            try:
                prior = json.loads(checkpoint.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise BoundedCampaignAuthorizationError(
                    "Unverifiable prior attempt; no provider replay") from exc
            _require(type(prior) is dict and prior.get("last_error") is None,
                     "PRIOR_STAGE_FAILURE_HOLD: previously failed paid campaign "
                     "cannot restart unchanged after a new process invocation")
        return {"status": "REUSED_EXACT_BOUNDED_PROVIDER_SCOPE",
                "publication_authorized": False,
                "stage_retries": stage_retries}
    use_standing = bool(standing_private_development and not explicit_authorization)
    if use_standing:
        from microgen_private_dev_policy import (
            eligible_private_development, ledger_identity, LEDGER_FOLDER,
        )
        _require(eligible_private_development(
            repo=repo, source_root=source_root, work_root=root,
            stop_after=stop_after, stage_retries=stage_retries,
            multipart=multipart,
        ), "STANDING_PRIVATE_DEVELOPMENT_SCOPE_INVALID: HP, private G2, "
           "single source and zero retries only")
    else:
        _require(explicit_authorization,
                 "NO_STANDING_PROVIDER_SCOPE: use the owner-approved "
                 "bounded private development policy, or explicitly "
                 "authorize a different provider campaign")
    root.mkdir(parents=True, exist_ok=True)
    ledger = None
    if use_standing:
        folder = root.parent / LEDGER_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        ledger = folder / (ledger_identity(scope) + ".json")
        _require(not ledger.is_symlink(),
                 "Unsafe autonomous campaign ledger")
        # One first-use paid scope per immutable source+Git commit; a new
        # directory or chat cannot reset a prior possibly billed attempt.
        try:
            with ledger.open("x", encoding="utf-8") as handle:
                json.dump({"source_sha256": scope["source_sha256"],
                           "code_revision": scope["code_revision"],
                           "work_root": str(root),
                           "status": "FINITE_PRIVATE_OWNER_STANDING_GRANT"},
                          handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            raise BoundedCampaignAuthorizationError(
                "STANDING_CAMPAIGN_ALREADY_USED: source/code already "
                "has a paid private campaign; no duplicate launch") from exc
    record = {
        "schema_version": 1, "status": STATUS,
        "scope": scope, "max_stage_retries": stage_retries,
        "publication_authorized": False,
    }
    # Exclusive creation prevents replacing a prior owner's campaign scope.
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise BoundedCampaignAuthorizationError(
            "Concurrent campaign authorization: do not overwrite") from exc
    return {"status": ("FROZEN_STANDING_PRIVATE_DEVELOPMENT_SCOPE"
                       if use_standing else "FROZEN_ONE_TIME_PROVIDER_SCOPE"),
            "publication_authorized": False,
            "stage_retries": stage_retries}
