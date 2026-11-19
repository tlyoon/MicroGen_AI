"""Version-controlled, executable recognition of recurring MicroGen_AI blockers.

The registry classifies verified, *known* failures. It does not dynamically
execute handlers, grant spending, waive scientific gates or run LLMs. Normal
recovery handlers continue inside their existing production stages; a known
unresolved deterministic QA failure receives a durable source-bound hold.

Unknown or transient cases retain the finite preexisting retry policy.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

REGISTRY_NAME = "microgen_recovery_registry_v6.json"
DECISION_NAME = ".microgen_recovery_v6.json"
ALLOWED_CLASSES = {"scientific_qa", "infrastructure", "software",
                   "data", "authorization", "orchestration"}
ALLOWED_DISPOSITIONS = {"DETERMINISTIC_HOLD", "PAUSED_EXTERNAL_DEPENDENCY",
                        "UNRESOLVED_EXTERNAL_EFFECT_HOLD"}
CLASS_RE = re.compile(
    r"^[ \t]*(?P<exception>[A-Za-z_][A-Za-z_0-9]*)"
    r":[ \t]+(?P<message>[^\r\n]{1,600})[ \t]*$",
    flags=re.MULTILINE,
)


class RecoveryRegistryError(RuntimeError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_registry(folder: Path) -> dict:
    path = Path(folder) / REGISTRY_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise RecoveryRegistryError("Missing or malformed committed recovery registry") from exc
    if (not isinstance(data, dict) or set(data) !=
            {"schema_version", "registry_id", "entries"}
            or data["schema_version"] != 6
            or data["registry_id"] != "MICROGEN_AI_ORIGINAL_API_V6"
            or not isinstance(data["entries"], list)
            or not data["entries"]):
        raise RecoveryRegistryError("Recovery registry schema or project mismatch")
    seen = set()
    fields = {"id", "classification", "stages", "exception", "message_marker",
              "disposition", "handler", "preconditions", "verification",
              "historical_evidence", "last_validated", "max_unmodified_retries",
              "publication_allowed"}
    for item in data["entries"]:
        if (not isinstance(item, dict) or set(item) != fields
                or not isinstance(item["id"], str)
                or not re.fullmatch(r"MGA-[A-Z0-9-]{5,100}", item["id"])
                or item["id"] in seen
                or item["classification"] not in ALLOWED_CLASSES
                or not isinstance(item["stages"], list)
                or not item["stages"]
                or any(not isinstance(x, str) or not x for x in item["stages"])
                or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*",
                                    item["exception"])
                or not isinstance(item["message_marker"], str)
                or len(item["message_marker"]) > 100
                or item["disposition"] not in ALLOWED_DISPOSITIONS
                or item["max_unmodified_retries"] != 0
                or item["publication_allowed"] is not False
                or not all(isinstance(item[f], str) and item[f]
                           for f in ("handler", "preconditions",
                                     "verification", "historical_evidence",
                                     "last_validated"))):
            raise RecoveryRegistryError("Untrusted or incomplete recovery entry")
        seen.add(item["id"])
    return data


def classify_log_attempt(stage_name: str, output: bytes,
                         *, registry_folder: Path) -> dict | None:
    """Look only at the current attempt's actual Python traceback.

    Never accept a keyword appearing in a PDF, prompt, narration or historic
    earlier log as evidence of a current software exception.
    """
    if (not isinstance(stage_name, str) or not stage_name
            or not isinstance(output, bytes)):
        raise ValueError("Malformed recovery classification inputs")
    data = load_registry(registry_folder)
    body = output[-1024 * 1024:].decode("utf-8", errors="replace")
    traceback_at = body.rfind("Traceback (most recent call last):")
    if traceback_at < 0:
        return None
    tail = body[traceback_at:]
    # Recognize whole, unindented terminal Python exception lines. Using
    # splitlines avoids newline/escape differences between Windows and Linux.
    # A message quoted within source or indented inside a traceback is not
    # an actual terminal exception.
    lines = []
    for line in tail.splitlines():
        if not line or line[:1].isspace() or ": " not in line:
            continue
        name, sep, message = line.partition(": ")
        # Python renders exceptions imported from other modules with their
        # fully qualified class name: module.VerifiedAcousticReplayError.
        # Classify the final actual exception class without requiring it to
        # be defined in the child driver. Reject non-identifier decorations,
        # arbitrary log phrases or an unbounded namespace chain.
        identifiers=name.split(".")
        if (1 <= len(identifiers) <= 4
                and all(x.isidentifier() for x in identifiers)
                and 1 <= len(message) <= 600):
            lines.append((identifiers[-1], message.strip()))
    if not lines:
        return None
    # Earlier chained exceptions are not the final exception.
    name, message = lines[-1]
    matches = [
        item for item in data["entries"]
        if stage_name in item["stages"] and name == item["exception"]
        and (not item["message_marker"]
             or item["message_marker"] in message)
    ]
    if not matches:
        return None
    # An exact historical failure pattern takes precedence over an older
    # generic same-exception fallback. Other overlaps are still ambiguous:
    # never select by insertion order or silently waive a QA hold.
    if len(matches) > 1:
        strongest=max(len(item["message_marker"]) for item in matches)
        matches=[
            item for item in matches
            if len(item["message_marker"]) == strongest
        ]
    if len(matches) != 1:
        raise RecoveryRegistryError("Ambiguous overlapping verified recovery signatures")
    item = matches[0]
    return {
        "failure_id": item["id"],
        "category": item["classification"],
        "exception": name,
        "disposition": item["disposition"],
        "handler": item["handler"],
        "max_unmodified_retries": item["max_unmodified_retries"],
        "stage": stage_name,
        "registry_sha256": digest(Path(registry_folder) / REGISTRY_NAME),
    }


def classify_runtime_error(stage_name: str, error: Exception, *,
                           registry_folder: Path) -> dict | None:
    """Classify a batch-runner-generated local pause or uncertain paid effect.

    The subprocess log classifier handles child tracebacks. This separate
    call handles parent-side bounded capacity pauses and post-send uncertain
    effects, recording them in the ordinary checkpoint without pretending
    they were a permanent source or scientific defect.
    """
    if not isinstance(stage_name, str) or not isinstance(error, Exception):
        raise ValueError("Invalid parent runtime recovery classification")
    registry = load_registry(registry_folder)
    kind=type(error).__name__
    message=str(error)
    hits=[
        item for item in registry["entries"]
        if stage_name in item["stages"]
        and kind == item["exception"]
        and item["disposition"] in {
            "PAUSED_EXTERNAL_DEPENDENCY","UNRESOLVED_EXTERNAL_EFFECT_HOLD"
        }
        and item["message_marker"]
        and message.startswith(item["message_marker"]+":")
    ]
    if len(hits)>1:
        raise RecoveryRegistryError("Ambiguous parent runtime recovery signatures")
    if not hits:
        return None
    item=hits[0]
    return {
        "failure_id":item["id"],
        "category":item["classification"],
        "exception":kind,
        "disposition":item["disposition"],
        "handler":item["handler"],
        "max_unmodified_retries":item["max_unmodified_retries"],
        "stage":stage_name,
        "registry_sha256":digest(Path(registry_folder)/REGISTRY_NAME),
    }


def persist_stage_decision(stage: Path, decision: dict, *,
                           attempt_number: int) -> dict:
    """Atomic, retry-safe private decision; no raw provider text or tokens.

    Normal process_one's subchapter ownership lock serializes mutations. On
    interruption the receipt survives and can be reconciled with the
    separately durable checkpoint; it never implies the failed QA passed.
    """
    stage = Path(stage)
    if (not stage.is_dir() or stage.is_symlink()
            or attempt_number < 1 or attempt_number > 100
            or not isinstance(decision, dict)
            or decision.get("disposition") != "DETERMINISTIC_HOLD"):
        raise RecoveryRegistryError("Unsafe recovery decision persistence")
    safe_keys = {"failure_id", "category", "exception", "disposition", "handler",
                 "max_unmodified_retries", "stage", "registry_sha256"}
    if set(decision) != safe_keys:
        raise RecoveryRegistryError("Malformed or extra recovery decision properties")
    for key in ("failure_id", "exception", "stage", "registry_sha256"):
        if not isinstance(decision[key], str) or not decision[key]:
            raise RecoveryRegistryError("Invalid recovery receipt field")
    try:
        source_sha = digest(stage / "source.pdf")
        code_sha = digest(stage / "microgen_batch.py")
    except OSError as exc:
        raise RecoveryRegistryError("Cannot bind recovery to source and batch runner") from exc
    record = {
        "schema_version": 6,
        "project": "MicroGen_AI",
        "source_sha256": source_sha,
        "batch_runner_sha256": code_sha,
        "attempt_number": attempt_number,
        "accepted_as_qa": False,
        "paid_retry_authorized": False,
        "publication_allowed": False,
        "next_eligible_operation": "HOLD_SAME_STAGE_UNTIL_VERIFIED_NEW_EVIDENCE",
        "decision": decision,
    }
    path = stage / DECISION_NAME
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RecoveryRegistryError("Corrupted existing recovery decision") from exc
        if existing == record:
            return existing
        # Never clobber another live/ambiguous attempt or circumvent its hold.
        raise RecoveryRegistryError("Recovery decision exists with different identity")
    fd, tmp = tempfile.mkstemp(prefix=".microgen_recovery_", suffix=".tmp",
                                dir=str(stage))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, sort_keys=True, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        # Stage already has a crash-recoverable exclusive owner lock.
        if path.exists():
            raise RecoveryRegistryError("Concurrent duplicate recovery decision")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return record


def verified_stage_hold(stage: Path, stage_name: str) -> bool:
    """Reconcile a recorded known QA failure after sudden process termination.

    Called by the normal batch stage runner *before* provider submission.
    A crash between saving this durable receipt and the batch checkpoint
    must never reset paid retries or skip an unresolved scientific gate.
    """
    stage = Path(stage)
    receipt = stage / DECISION_NAME
    if not receipt.exists():
        return False
    if receipt.is_symlink() or not receipt.is_file():
        raise RecoveryRegistryError("Unsafe recovery hold receipt")
    try:
        raw = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecoveryRegistryError("Unreadable or corrupt recovery hold") from exc
    if (not isinstance(raw, dict) or raw.get("schema_version") != 6
            or raw.get("project") != "MicroGen_AI"
            or raw.get("accepted_as_qa") is not False
            or raw.get("paid_retry_authorized") is not False
            or raw.get("publication_allowed") is not False
            or raw.get("next_eligible_operation") !=
               "HOLD_SAME_STAGE_UNTIL_VERIFIED_NEW_EVIDENCE"):
        raise RecoveryRegistryError("Unverified or forged recovery receipt")
    d = raw.get("decision")
    if not isinstance(d, dict):
        raise RecoveryRegistryError("Missing prior failure classification")
    if d.get("stage") != stage_name:
        return False  # The current independent earlier stage may still run.
    registry = load_registry(stage)
    matches = [
        item for item in registry["entries"]
        if item["id"] == d.get("failure_id")
        and item["exception"] == d.get("exception")
        and item["disposition"] == d.get("disposition")
        and item["handler"] == d.get("handler")
        and stage_name in item["stages"]
    ]
    if len(matches) != 1:
        raise RecoveryRegistryError("Prior recovery signature changed or retired")
    if (raw.get("source_sha256") != digest(stage/"source.pdf")
            or raw.get("batch_runner_sha256") != digest(stage/"microgen_batch.py")
            or d.get("registry_sha256") != digest(stage/REGISTRY_NAME)):
        raise RecoveryRegistryError(
            "Source, runner, or recovery registry changed after a prior "
            "deterministic hold; require a fresh verified bounded campaign"
        )
    return True
