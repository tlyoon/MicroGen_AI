"""Restart-safe, finite, exact-hash replacement of private timed acoustic assets.

A durable backup and inventory precede the FIRST modification. Each file
switches using same-directory os.replace, so after process loss the file is
either its complete old or its complete new identity. The no-provider normal
runner restores the old evidence on an interrupted transaction. A successful
transaction requires both source PCM timing and voice provenance revalidation.
The acoustic acceptance gate remains separate and mandatory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable

JOURNAL = ".microgen_timed_acoustic_transaction"
MAX_ASSETS = 24


class TimedAcousticTransactionError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        h=hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _source_signature(stage:Path) -> dict:
    return {
        name:_sha(stage/name)
        for name in ("source.pdf","slides.pdf","script_tts.json")
    }


def _relative(stage:Path, name:str) -> Path:
    if (not isinstance(name,str) or not name or len(name)>120
            or "\\" in name or ":" in name or name.startswith("/")
            or any(x in ("","..",".") for x in name.split("/"))
            or not re.fullmatch(r"[A-Za-z0-9_.\-/]+",name)):
        raise TimedAcousticTransactionError("Unsafe target path")
    path=stage/name
    if (path.is_symlink() or path.parent.is_symlink()
            or stage.resolve() not in path.resolve().parents):
        raise TimedAcousticTransactionError("Unsafe transactional asset")
    return path


def _atomic_write_bytes(dest:Path,source:Path) -> None:
    # Copy into a private file on the same volume and fsync before os.replace.
    handle,name=tempfile.mkstemp(prefix=".microgen-acoustic-file-",dir=dest.parent)
    try:
        with os.fdopen(handle,"wb") as out, source.open("rb") as inp:
            for piece in iter(lambda:inp.read(1024*1024),b""):
                out.write(piece)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name,dest)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read_plan(stage:Path) -> tuple[Path,dict]:
    journal=stage/JOURNAL
    if journal.is_symlink() or not journal.is_dir():
        raise TimedAcousticTransactionError("Unsafe pending acoustic journal")
    plan_path=journal/"plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise TimedAcousticTransactionError("Uncommitted or malformed acoustic journal")
    try:
        plan=json.loads(plan_path.read_text(encoding="utf8"))
    except (OSError,UnicodeError,ValueError) as exc:
        raise TimedAcousticTransactionError("Unreadable acoustic journal") from exc
    if (not isinstance(plan,dict) or set(plan)!={"schema_version","status",
            "publication_allowed","source_sha256","files"}
            or plan["schema_version"]!=1 or plan["status"]!="INSTALLING"
            or plan["publication_allowed"] is not False
            or not isinstance(plan["files"],dict)
            or not 1<=len(plan["files"])<=MAX_ASSETS
            or plan["source_sha256"]!=_source_signature(stage)):
        raise TimedAcousticTransactionError("Source or journal identity changed")
    for idx,(name,entry) in enumerate(plan["files"].items()):
        _relative(stage,name)
        if (not isinstance(entry,dict) or set(entry)!={"old","new"}
                or not isinstance(entry["old"],str)
                or not re.fullmatch("[0-9a-f]{64}",entry["old"])
                or not isinstance(entry["new"],str)
                or not re.fullmatch("[0-9a-f]{64}",entry["new"])
                or not (journal/"backups"/f"{idx:03}.original").is_file()
                or _sha(journal/"backups"/f"{idx:03}.original")!=entry["old"]):
            raise TimedAcousticTransactionError("Corrupt old acoustic evidence")
    return journal,plan


def recover_interrupted_timed_acoustic(stage:Path) -> str:
    """No-provider, exact-hash recovery of interrupted private replacement.

    Unknown bytes are never overwritten: a concurrent human change or
    incomplete external operation requires an explicit evidence hold.
    """
    stage=Path(stage)
    journal=stage/JOURNAL
    if not journal.exists() and not journal.is_symlink():
        return "NO_TIMED_ACOUSTIC_TRANSACTION"
    folder,plan=_read_plan(stage)
    for name,entry in plan["files"].items():
        target=_relative(stage,name)
        if (not target.is_file() or _sha(target)
                not in (entry["old"],entry["new"])):
            raise TimedAcousticTransactionError(
                "UNRECOGNIZED_ACOUSTIC_ASSET_HOLD: refuse overwrite")
    for idx,name in enumerate(plan["files"]):
        _atomic_write_bytes(
            _relative(stage,name),folder/"backups"/f"{idx:03}.original")
    if any(_sha(_relative(stage,name))!=v["old"]
           for name,v in plan["files"].items()):
        raise TimedAcousticTransactionError("Acoustic rollback did not verify")
    shutil.rmtree(folder)
    return "INTERRUPTED_TIMED_AUDIO_ROLLED_BACK_OFFLINE"


def install_timed_acoustic(
    stage:Path,
    replacements:dict[str,Path],
    validate:Callable[[],object],
) -> dict:
    """Commit measured cue/slide/provenance outputs, or fully roll back."""
    stage=Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise TimedAcousticTransactionError("Unsafe private stage")
    if not isinstance(replacements,dict) or not 1<=len(replacements)<=MAX_ASSETS:
        raise TimedAcousticTransactionError("Unbounded acoustic replacement")
    if (stage/JOURNAL).exists() or (stage/JOURNAL).is_symlink():
        raise TimedAcousticTransactionError("Prior acoustic journal requires recovery")
    snapshot=_source_signature(stage)
    entries={}
    for name,candidate in replacements.items():
        target=_relative(stage,name)
        candidate=Path(candidate)
        if (not target.is_file() or not candidate.is_file()
                or candidate.is_symlink() or candidate.resolve()==target.resolve()):
            raise TimedAcousticTransactionError("Missing or unsafe acoustic candidate")
        entries[name]={"old":_sha(target),"new":_sha(candidate)}
    journal=stage/JOURNAL
    journal.mkdir(exist_ok=False)
    try:
        backup=journal/"backups"
        backup.mkdir()
        for idx,name in enumerate(entries):
            destination=backup/f"{idx:03}.original"
            shutil.copy2(_relative(stage,name),destination)
            with destination.open("r+b") as stream:
                stream.flush()
                os.fsync(stream.fileno())
            if _sha(destination)!=entries[name]["old"]:
                raise TimedAcousticTransactionError("Backup drift before acoustic commit")
        plan={
            "schema_version":1,
            "status":"INSTALLING",
            "publication_allowed":False,
            "source_sha256":snapshot,
            "files":entries,
        }
        with (journal/"plan.json").open("x",encoding="utf8") as out:
            json.dump(plan,out,indent=2)
            out.flush()
            os.fsync(out.fileno())
        for name,candidate in replacements.items():
            _atomic_write_bytes(_relative(stage,name),Path(candidate))
            if _sha(_relative(stage,name))!=entries[name]["new"]:
                raise TimedAcousticTransactionError("Candidate changed on commit")
        validate()
        if _source_signature(stage)!=snapshot:
            raise TimedAcousticTransactionError("Source modified by acoustic repair")
        shutil.rmtree(journal)
        return {
            "status":"TIMED_ACOUSTIC_ASSETS_TRANSACTIONALLY_INSTALLED",
            "assets":len(entries),"publication_allowed":False,
        }
    except Exception:
        if (journal/"plan.json").is_file():
            recover_interrupted_timed_acoustic(stage)
        else:
            # No source asset was changed before a committed journal.
            shutil.rmtree(journal)
        raise
