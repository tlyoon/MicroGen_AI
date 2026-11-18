"""Crash-safe, zero-overwrite import of already verified original PCM cues.

The source/PDF/voice verification is performed by the calling production
reuse gate. This module moves a finite inventory into an empty private stage
using a durable SHA-bound journal and exclusive same-volume hard links.
An interrupted batch removes ONLY exact expected imports offline; unknown
bytes or changed source become a deterministic hold, never a paid retry.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Callable

from microgen_timed_acoustic_transaction import _relative

JOURNAL=".microgen_exclusive_preacoustic_import"
MAX_FILES=300
MAX_BYTES=500_000_000


class ExclusiveAudioImportError(RuntimeError):
    pass


def sha(path:Path)->str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def source_proof(stage:Path)->dict:
    return {name:sha(stage/name) for name in (
        "source.pdf","slides.pdf","script_tts.json")}


def recover_interrupted_audio_import(stage:Path)->str:
    stage=Path(stage)
    journal=stage/JOURNAL
    if not journal.exists() and not journal.is_symlink():
        return "NO_PREACOUSTIC_IMPORT_PENDING"
    if journal.is_symlink() or not journal.is_dir():
        raise ExclusiveAudioImportError("Unsafe preacoustic import journal")
    path=journal/"plan.json"
    if not path.exists():
        # Nothing is linked before the valid plan is written and fsynced.
        if list(journal.iterdir()):
            raise ExclusiveAudioImportError(
                "UNVERIFIED_PREACOUSTIC_IMPORT_JOURNAL_HOLD")
        journal.rmdir()
        return "UNSTARTED_PREACOUSTIC_IMPORT_CLEARED"
    if path.is_symlink() or not path.is_file() or path.stat().st_size>40000:
        raise ExclusiveAudioImportError("Unsafe preacoustic import plan")
    try:
        data=json.loads(path.read_text(encoding="utf8"))
    except (OSError,UnicodeError,ValueError) as exc:
        raise ExclusiveAudioImportError("Unreadable import plan") from exc
    if (not isinstance(data,dict)
            or set(data)!={"schema_version","publication_allowed",
                             "source_sha256","assets"}
            or data["schema_version"]!=1
            or data["publication_allowed"] is not False
            or data["source_sha256"]!=source_proof(stage)
            or not isinstance(data["assets"],dict)
            or not 1<=len(data["assets"])<=MAX_FILES):
        raise ExclusiveAudioImportError("Source or import plan changed")
    assets=data["assets"]
    for name,digest in assets.items():
        path=_relative(stage,name)
        if (not isinstance(digest,str) or len(digest)!=64
                or any(c not in "0123456789abcdef" for c in digest)
                or (path.exists() and
                    (not path.is_file() or sha(path)!=digest))):
            raise ExclusiveAudioImportError(
                "UNRECOGNIZED_IMPORTED_AUDIO_HOLD: refuse unlink")
    for name in reversed(assets):
        path=_relative(stage,name)
        if path.is_file():
            path.unlink()
    for dirname in ("highlight_chunks",".microgen_tts_cache"):
        folder=stage/dirname
        if folder.exists() and folder.is_dir() and not list(folder.iterdir()):
            folder.rmdir()
    journal.rmdir() if not list(journal.iterdir()) else shutil.rmtree(journal)
    return "INTERRUPTED_ORIGINAL_CUES_REMOVED_OFFLINE"


def import_verified_audio_assets(
    stage:Path,candidates:dict[str,Path],accept:Callable[[],None]
)->dict:
    stage=Path(stage)
    if (stage.is_symlink() or not stage.is_dir()
            or not isinstance(candidates,dict)
            or not 1<=len(candidates)<=MAX_FILES):
        raise ExclusiveAudioImportError("Unbounded or unsafe audio import")
    journal=stage/JOURNAL
    if journal.exists() or journal.is_symlink():
        raise ExclusiveAudioImportError("Pending audio import must recover first")
    before=source_proof(stage)
    digests={}
    length=0
    for name,candidate in candidates.items():
        path=_relative(stage,name)
        candidate=Path(candidate)
        if (path.exists() or path.is_symlink()
                or candidate.is_symlink() or not candidate.is_file()):
            raise ExclusiveAudioImportError("Refuse overwrite of any imported asset")
        digests[name]=sha(candidate)
        length+=candidate.stat().st_size
    if length>MAX_BYTES:
        raise ExclusiveAudioImportError("Audio import byte budget exceeded")
    journal.mkdir(exist_ok=False)
    try:
        with (journal/"plan.json").open("x",encoding="utf8") as stream:
            json.dump({
                "schema_version":1,"publication_allowed":False,
                "source_sha256":before,"assets":digests,
            },stream,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        for name,candidate in candidates.items():
            destination=_relative(stage,name)
            destination.parent.mkdir(parents=True,exist_ok=True)
            os.link(candidate,destination)
            if sha(destination)!=digests[name]:
                raise ExclusiveAudioImportError("Source PCM changed after exclusive link")
        if source_proof(stage)!=before:
            raise ExclusiveAudioImportError("Original PDF or source script changed")
        accept()
        if source_proof(stage)!=before:
            raise ExclusiveAudioImportError("Source changed after import acceptance")
        shutil.rmtree(journal)
        return {"status":"ORIGINAL_PCM_IMPORTED_AND_TTS_CHECKPOINTED",
                "asset_count":len(digests),"publication_allowed":False}
    except Exception:
        recover_interrupted_audio_import(stage)
        raise
