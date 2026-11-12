"""Automatic, non-billable reuse of independently verified upstream G2 stages.

Invoked by the normal owner-authorized HP private G2 pipeline BEFORE any
provider stage. A new code revision modifying only the cue/TTS path can
reuse original-PDF/figure/slide/narration/science evidence when ALL six
old and new stage validators and original dependency fingerprints pass.
Never carries over TTS, acoustic/video receipts, failed checkpoints or a
provider authorization. A new committed revision and a finite standing
campaign are still required for paid work.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

UPSTREAM = (
    "figure_extraction", "figure_mapping", "figure_merge",
    "slides", "narration", "science_qa",
)
RECEIPT = ".microgen_verified_upstream_import.json"
ALLOW_DIRS = (
    "pages", "crops", ".microgen_mapping_cache",
    ".microgen_narration_batches", ".microgen_structural_reflow",
)
ALLOW_FILES = {
    "figure_extraction_receipt.json",
    "figure_composition_receipt.json",
    ".microgen_source_caption_vector_recovery.json",
    ".microgen_structural_reflow_receipt.json",
    ".microgen_autonomous_science_qa.json",
    "slides.pdf", "slides.tex", "slides.log",
    "script.txt", "script_tts.json",
}
ALLOW_PATTERN = re.compile(r"(?:Figure [0-9]+(?:\.[0-9]+)?(?:[a-z])?\.png|slide[1-9][0-9]*\.pdf)\Z")
OWNER_RECEIPT = ".microgen_bounded_provider_authorization.json"


class UpstreamReuseError(RuntimeError):
    """Never accept a questionable cached scientific/lecture artifact."""


def _sha(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read_json(path: Path) -> dict | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_filetree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise UpstreamReuseError("Source reuse directory is unsafe")
    total = 0
    size = 0
    for item in root.rglob("*"):
        total += 1
        if total > 4000 or item.is_symlink():
            raise UpstreamReuseError("Untrusted source-reuse path or file inventory")
        if item.is_file():
            size += item.stat().st_size
        if size > 750_000_000:
            raise UpstreamReuseError("Source reuse exceeds bounded private scratch budget")


def verify_import_receipt(stage: Path) -> dict | None:
    """Verify portable source/deck/commit proof, independent of old workroot."""
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.exists():
        return None
    data=_read_json(path)
    if (data is None or data.get("schema_version")!=1
            or data.get("status")!="SIX_UPSTREAM_SOURCE_BOUND_STAGES_REVERIFIED"
            or data.get("publication_allowed") is not False
            or data.get("new_audio_reused") is not False
            or data.get("stages")!=list(UPSTREAM)
            or data.get("source_pdf_sha256")!=_sha(stage/"source.pdf")
            or data.get("origin_slides_pdf_sha256")!=_sha(stage/"slides.pdf")):
        raise UpstreamReuseError("Imported upstream provenance drifted")
    vector_receipt = stage / ".microgen_source_caption_vector_recovery.json"
    vector_sha = data.get("source_caption_vector_recovery_receipt_sha256")
    if bool(vector_sha) != vector_receipt.exists():
        raise UpstreamReuseError("Imported source-caption provenance missing or unexpected")
    if vector_sha and (vector_receipt.is_symlink() or not vector_receipt.is_file()
                       or _sha(vector_receipt) != vector_sha):
        raise UpstreamReuseError("Imported source-caption provenance drifted")
    cp=_read_json(stage/".microgen_checkpoint.json")
    if cp is not None and cp.get("package_commit") != data.get(
            "current_code_revision"):
        raise UpstreamReuseError("Current runner revision differs from import")
    return {"receipt_sha256":_sha(path),
            "source_pdf_sha256":data["source_pdf_sha256"],
            "stages":data["stages"]}


def _candidate(repo_root: Path, candidate_work: Path, subchapter: str,
               source_sha: str, dest: Path, *, stage_valid, quality) -> tuple | None:
    """Check receipt, six completed upstream stages and old code fingerprints."""
    receipt = _read_json(candidate_work / OWNER_RECEIPT)
    if receipt is None or receipt.get("schema_version") != 1:
        return None
    scope = receipt.get("scope", {})
    if (receipt.get("publication_authorized") is not False
            or not isinstance(scope, dict)
            or scope.get("source_sha256") != source_sha
            or scope.get("host") != "hp"
            or scope.get("stop_after") != "acceptance"):
        return None
    stage = candidate_work / subchapter
    cp = _read_json(stage / ".microgen_checkpoint.json")
    if cp is None or cp.get("package_commit") != scope.get("code_revision"):
        return None
    completed = cp.get("completed")
    fingerprints = cp.get("dependency_fingerprints")
    if not isinstance(completed, dict) or not isinstance(fingerprints, dict):
        return None
    if any(not completed.get(name) for name in UPSTREAM):
        return None
    if not (stage / "source.pdf").is_file() or (stage / "source.pdf").is_symlink():
        return None
    if _sha(stage / "source.pdf") != source_sha:
        return None
    # A saved pass is never enough; recompute each OLD fingerprint and recheck
    # six actual old outputs before considering the candidate for import.
    for name in UPSTREAM:
        if fingerprints.get(name) != quality.dependency_fingerprint(stage, name):
            return None
        if not stage_valid(stage, name, dest):
            return None
    return (str(completed["science_qa"]), stage)


def _copy_evidence(old: Path, target: Path) -> list[str]:
    copied = []
    for dirname in ALLOW_DIRS:
        source = old / dirname
        if source.is_dir():
            _safe_filetree(source)
            shutil.copytree(source, target / dirname)
            copied.append(dirname)
    names = set(ALLOW_FILES)
    names.update(p.name for p in old.iterdir()
                 if p.is_file() and ALLOW_PATTERN.fullmatch(p.name))
    for name in sorted(names):
        source = old / name
        if not source.is_file():
            continue
        if source.is_symlink() or (target / name).exists():
            raise UpstreamReuseError(f"Unsafe upstream import destination: {name}")
        shutil.copy2(source, target / name)
        if _sha(source) != _sha(target / name):
            raise UpstreamReuseError("Source-bound evidence copy hash drift")
        copied.append(name)
    return copied


def maybe_import_verified_upstream(
    *, repo: Path, source_root: Path, work_root: Path,
    subchapter: str, source_file: Path, dest: Path, commit: str,
    source_wait: float, prepare_stage, stage_valid, mark_complete,
    quality,
) -> dict | None:
    """Auto-select newest fully verified source-bound prior HP private G2.

    Called only inside a *new* owner standing private G2 scope. Never reuses
    a terminal TTS checkpoint; only independently passed upstream stages.
    If no eligible prior campaign exists, normal fresh generation proceeds.
    """
    work_root = Path(work_root)
    if (work_root / subchapter).exists():
        return None
    root = work_root.parent
    if not root.is_dir() or work_root.parent != root:
        raise UpstreamReuseError("Unsafe private scratch root")
    source_file = Path(source_file)
    if source_file.is_symlink() or not source_file.is_file():
        raise UpstreamReuseError("Original source is missing or linked")
    source_sha = _sha(source_file)
    entries = []
    for entry in sorted(root.iterdir()):
        if (entry == work_root or entry.is_symlink()
                or not entry.is_dir() or entry.name.startswith(".")):
            continue
        if not (entry / OWNER_RECEIPT).is_file():
            continue
        try:
            found = _candidate(
                root, entry, subchapter, source_sha, dest,
                stage_valid=stage_valid, quality=quality)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            continue
        if found is not None:
            entries.append(found)
    if not entries:
        return None
    entries.sort(key=lambda record: record[0], reverse=True)
    if len(entries) > 1 and entries[0][0] == entries[1][0]:
        raise UpstreamReuseError("Ambiguous equally recent science-approved source")
    _, old = entries[0]
    # Use a temporary SOURCE+CURRENTRUNNER stage; no failed-old work or
    # symlinks are promoted before ALL new-code stage validators pass.
    with tempfile.TemporaryDirectory(
        prefix=".microgen-verified-upstream-", dir=work_root
    ) as temp_root:
        stage, cp, checkpoint_path = prepare_stage(
            repo, source_root, Path(temp_root), subchapter, source_wait, commit)
        copied = _copy_evidence(old, stage)
        for name in UPSTREAM:
            if not stage_valid(stage, name, dest):
                raise UpstreamReuseError(
                    f"Current-code source QA failed imported {name}; "
                    "no old acceptance reused")
        summary = {
            "schema_version": 1,
            "status": "SIX_UPSTREAM_SOURCE_BOUND_STAGES_REVERIFIED",
            "source_pdf_sha256": source_sha,
            "origin_stage": str(old),
            "origin_slides_pdf_sha256": _sha(old / "slides.pdf"),
            "source_caption_vector_recovery_receipt_sha256": (
                _sha(stage / ".microgen_source_caption_vector_recovery.json")
                if (stage / ".microgen_source_caption_vector_recovery.json").is_file()
                else None),
            "current_code_revision": commit,
            "stages": list(UPSTREAM),
            "copied_items": copied,
            "new_audio_reused": False,
            "new_model_requests": False,
            "publication_allowed": False,
        }
        (stage / RECEIPT).write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        for name in UPSTREAM:
            mark_complete(cp, checkpoint_path, name, stage)
        # No existing accepted workroot stage may be overwritten, including
        # if another worker raced to start after the original check.
        final_stage = work_root / subchapter
        if final_stage.exists() or final_stage.is_symlink():
            raise UpstreamReuseError("Concurrent stage already exists")
        os.rename(stage, final_stage)
    return {
        "status": summary["status"],
        "from": old.parent.name,
        "stages": list(UPSTREAM),
        "audio_reused": False,
    }
