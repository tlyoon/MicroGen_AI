"""Fail-closed, preassigned cross-PC ownership without external cloud services.

A Google Drive-synced JSON manifest assigns each subchapter to ONE immutable
hostname. Unlike GCS, this is NOT a distributed mutex: all workers must share
the same pre-agreed manifest SHA256, and no automatic failover is possible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from pathlib import Path
from typing import Any

from microgen_ownership import LeaseLost

_CHAPTER_RE = re.compile(r"\d+\.\d+\Z")
_HOST_RE = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,79}\Z")
_CAMPAIGN_RE = re.compile(r"[A-Za-z0-9_.:-]{1,120}\Z")


class AssignmentError(RuntimeError):
    """Invalid, out-of-date, or disallowed subchapter assignment."""


class AssignmentDenied(AssignmentError):
    """Another registered host is the one authorized to run this target."""


def configured_gemini_lane() -> str:
    """Find the existing Drive FIFO path even in a stale Windows agent session."""
    configured = os.environ.get("MICROGEN_GEMINI_LANE_DIR", "").strip()
    if configured or os.name != "nt":
        return configured
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            raw, _ = winreg.QueryValueEx(key, "MICROGEN_GEMINI_LANE_DIR")
        if isinstance(raw, str):
            return os.path.expandvars(raw.strip())
    except (ImportError, OSError):
        pass
    return ""


def machine_id() -> str:
    name = socket.gethostname().strip().upper()
    if not _HOST_RE.fullmatch(name):
        raise AssignmentError("Host identity is invalid: cannot establish exclusive assignment")
    return name


def manifest_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validated_manifest(raw: bytes, *, campaign: str, source_root: Path) -> dict[str, Any]:
    try:
        info = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AssignmentError("Assignment manifest must be valid UTF-8 JSON") from exc
    if not isinstance(info, dict) or info.get("schema_version") != 1:
        raise AssignmentError("Unsupported assignment manifest schema")
    if not _CAMPAIGN_RE.fullmatch(campaign) or info.get("campaign_id") != campaign:
        raise AssignmentError("Campaign ID differs from pinned assignment manifest")
    root = info.get("source_root")
    if not isinstance(root, str) or not root.strip():
        raise AssignmentError("Assignment manifest needs an exact source_root")
    # Case-insensitive Windows path comparison; don't match an unrelated tree.
    actual = os.path.normcase(os.path.normpath(str(source_root.resolve())))
    agreed = os.path.normcase(os.path.normpath(str(Path(root).resolve())))
    if actual != agreed:
        raise AssignmentError("Source root does not match the agreed campaign")
    participants = info.get("participants")
    if not isinstance(participants, list) or not participants:
        raise AssignmentError("Nonempty participants are required")
    if any(not isinstance(p, str) or not _HOST_RE.fullmatch(p) or p != p.upper()
           for p in participants):
        raise AssignmentError("Participant hostnames must be uppercase, nonempty and safe")
    if len(set(participants)) != len(participants):
        raise AssignmentError("Duplicate host identities in participants")
    owners = info.get("owners")
    if not isinstance(owners, dict) or not owners:
        raise AssignmentError("Assignment manifest must assign at least one subchapter")
    if any(not isinstance(k, str) or not _CHAPTER_RE.fullmatch(k)
           or not isinstance(v, str) or v not in participants
           for k, v in owners.items()):
        raise AssignmentError("Each numeric subchapter must have one registered owner")
    if set(info) != {"schema_version", "campaign_id", "source_root", "participants", "owners"}:
        raise AssignmentError("Unexpected assignment manifest fields")
    return info


class DriveAssignedOwner:
    """Read-only manifest guard, retaining the stage-fencing assert_held API."""

    def __init__(self, path: Path, expected_sha256: str, campaign: str,
                 source_root: Path, subchapter: str, *, host: str | None = None):
        self.path = Path(path)
        self.digest = expected_sha256.strip().lower()
        self.campaign = campaign
        self.source_root = Path(source_root)
        self.subchapter = subchapter
        self.host = host or machine_id()
        if not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise AssignmentError("Explicit pinned 64-character manifest SHA256 required")
        if not _CHAPTER_RE.fullmatch(self.subchapter):
            raise AssignmentError("Invalid subchapter identifier")
        if self.host != machine_id():
            # No CLI override of the actual machine identity.
            raise AssignmentError("Host identity spoofing is not supported")

    def assert_held(self) -> None:
        try:
            payload = self.path.read_bytes()
        except OSError as exc:
            raise LeaseLost(f"Shared Drive assignment unavailable: {self.path}") from exc
        if hashlib.sha256(payload).hexdigest() != self.digest:
            raise LeaseLost("Assignment manifest SHA256 mismatch; stop, do not auto-reassign")
        try:
            manifest = validated_manifest(
                payload, campaign=self.campaign, source_root=self.source_root,
            )
        except AssignmentError as exc:
            raise LeaseLost(f"Assignment validation failed: {exc}") from exc
        expected = manifest["owners"].get(self.subchapter)
        if expected is None:
            raise AssignmentDenied(f"Subchapter {self.subchapter} is not assigned")
        if self.host not in manifest["participants"]:
            raise AssignmentDenied(f"Unregistered worker {self.host}")
        if expected != self.host:
            raise AssignmentDenied(
                f"Subchapter {self.subchapter} is assigned to {expected}, not {self.host}"
            )

    def __enter__(self):
        self.assert_held()
        return self

    def __exit__(self, _type, _value, _trace):
        # Static ownership has no lock to release. Reassignment requires a
        # new manifest and digest applied by an operator across every PC.
        return False
