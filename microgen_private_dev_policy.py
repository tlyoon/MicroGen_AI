"""Owner's standing, finite autonomous PRIVATE development contract (12 Nov 2026).

No recurring human approval for ordinary G2 lecture production or needed TTS.
Not an unlimited provider allowance: one first-use campaign per source-PDF
hash plus exact Git revision, no terminal replay, no publication, HP only.
The campaign authorizer owns durable receipts and the exclusive ledger.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import socket

STANDING_PRIVATE_DEVELOPMENT_ENABLED = True
ALLOWED_PRIVATE_ENDPOINTS = frozenset({"tts", "acceptance"})
MAX_STAGE_RETRIES = 0
MAX_SEMANTIC_SLIDES = 4
MAX_CLOUD_ATTEMPT_CHARACTERS = 40000
MAX_TTS_QUEUE_ROUNDS = 2
PRIMARY_TTS_MODEL = "gemini-3.8-flash-lite-tts"
GEMINI_FALLBACK_TTS_MODEL = "gemini-3.8-flash-tts"
CLOUD_FALLBACK_PROVIDER = "google_cloud_chirp3"
DEFAULT_VOICE = "Kore"
LEDGER_FOLDER = ".microgen_autonomous_private_campaigns"
OWNER_CONSENT_FILE = ".microgen_owner_private_development_consent.json"
OWNER_CONSENT_RECORD = {
    "schema_version": 1,
    "status": "OWNER_STANDING_G2_TTS_PRIVATE_DEVELOPMENT_2026_11_12",
    "host": "hp",
    "primary_tts_model": PRIMARY_TTS_MODEL,
    "gemini_fallback_model": GEMINI_FALLBACK_TTS_MODEL,
    "cloud_fallback_only": True,
    "max_cloud_attempt_characters": MAX_CLOUD_ATTEMPT_CHARACTERS,
    "max_stage_retries": MAX_STAGE_RETRIES,
    "publication_allowed": False,
}


def owner_local_grant_valid(checkpoint_root: Path) -> bool:
    """An explicit owner instruction is installed once in private HP storage.

    Cloning an otherwise public Git repository cannot silently authorize
    spending. The marker never contains a credential, API key or source PDF.
    """
    consent = Path(checkpoint_root) / OWNER_CONSENT_FILE
    if not consent.is_file() or consent.is_symlink():
        return False
    try:
        data = json.loads(consent.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    return data == OWNER_CONSENT_RECORD


def eligible_private_development(*, repo: Path, source_root: Path,
                                 work_root: Path, stop_after: str,
                                 stage_retries: int, multipart: bool) -> bool:
    """Restrict standing grant to the owner's isolated production workstation.

    Explicit --authorize-provider-usage retains its legacy behavior. No
    silent standing scope on CI, unrelated repos, publication or other PCs.
    """
    repo, source_root, work_root = (Path(p).resolve()
                                   for p in (repo, source_root, work_root))
    local = Path(os.environ.get("LOCALAPPDATA", "")).resolve()
    checkpoint_root = local / "MicroGen_AI_Checkpoints"
    return bool(
        STANDING_PRIVATE_DEVELOPMENT_ENABLED
        and os.name == "nt"
        and socket.gethostname().casefold() == "hp"
        and owner_local_grant_valid(checkpoint_root)
        and repo.name in {"G2_SERWAY24_RC_CODE_20261107", "MicroGen_AI"}
        and (repo / "microgen_batch.py").is_file()
        and (repo / "microgen_flash_tts.py").is_file()
        and stop_after in ALLOWED_PRIVATE_ENDPOINTS
        and type(stage_retries) is int and 0 <= stage_retries <= MAX_STAGE_RETRIES
        and multipart is False
        and work_root.parent == checkpoint_root
        and (not work_root.exists() or
             (work_root.is_dir() and (
                 not any(work_root.iterdir())
                 or (work_root / ".microgen_bounded_provider_authorization.json"
                     ).is_file())))
        and not source_root.is_relative_to(work_root)
    )


def ledger_identity(scope: dict) -> str:
    """One campaign for a given source hash + committed code revision.

    Changing a work-root filename or restarting ChatGPT cannot reset this
    finite permission. New development code can be tested in a new campaign.
    """
    relevant = {
        "source_sha256": scope["source_sha256"],
        "code_revision": scope["code_revision"],
        "host": scope["host"],
    }
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()


def freeze_standing_environment() -> None:
    """Apply the user's formal TTS choices before signing the campaign scope."""
    os.environ["MICROGEN_FORMAL_TTS_PROVIDER"] = "gemini"
    os.environ["MICROGEN_TTS_ENABLE_CLOUD_FALLBACK"] = "1"
    os.environ["MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS"] = str(
        MAX_CLOUD_ATTEMPT_CHARACTERS)
    os.environ["MICROGEN_TTS_VOICE"] = DEFAULT_VOICE
    os.environ["MICROGEN_TTS_QUEUE_ROUNDS"] = str(MAX_TTS_QUEUE_ROUNDS)
    os.environ["MICROGEN_TIMED_CUES"] = "1"
    os.environ["MICROGEN_TIMED_SEMANTIC_ASSIST"] = "1"
    os.environ["MICROGEN_TIMED_SEMANTIC_MAX_SLIDES"] = str(MAX_SEMANTIC_SLIDES)
    os.environ["MICROGEN_GEMINI_MAX_RETRIES"] = "0"
    os.environ["MICROGEN_GEMINI_SDK_RETRY_ATTEMPTS"] = "1"
