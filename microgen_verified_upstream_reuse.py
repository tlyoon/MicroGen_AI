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
FOUR_UPSTREAM = UPSTREAM[:4]
SIX_STATUS = "SIX_UPSTREAM_SOURCE_BOUND_STAGES_REVERIFIED"
FOUR_STATUS = "FOUR_UPSTREAM_SOURCE_BOUND_STAGES_REVERIFIED_VOICE_REBUILD"
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


def verify_import_receipt(stage: Path, *, require_cache: bool = True) -> dict | None:
    """Verify source/deck proof; private model response cache is not published."""
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.exists():
        return None
    data=_read_json(path)
    stages = data.get("stages") if isinstance(data, dict) else None
    expected = (SIX_STATUS if stages == list(UPSTREAM) else
                FOUR_STATUS if stages == list(FOUR_UPSTREAM) else None)
    if (data is None or data.get("schema_version")!=1
            or expected is None or data.get("status") != expected
            or data.get("publication_allowed") is not False
            or data.get("new_audio_reused") is not False
            or (expected == FOUR_STATUS and
                any(x in data.get("copied_items",[]) for x in (
                    "script.txt", "script_tts.json",
                    ".microgen_autonomous_science_qa.json",
                    ".microgen_narration_batches")))
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
    cached = data.get("source_bound_narration_response_cache")
    if cached is not None:
        if (expected != FOUR_STATUS or not isinstance(cached, dict)
                or cached.get("requires_exact_prompt_key_revalidation") is not True
                or cached.get("original_response_not_academic_qa") is not True):
            raise UpstreamReuseError("Untrusted model response cache receipt")
        manifest = cached.get("file_sha256")
        if (not isinstance(manifest, dict)
                or not 1 <= len(manifest) <= 40):
            raise UpstreamReuseError("Incomplete source-bound batch response cache")
        cache_folder = stage / ".microgen_narration_batches"
        if require_cache:
            # Working-stage acceptance requires every exact cached byte.
            # The final published copy deliberately omits raw model replies;
            # its signed manifest still binds this receipt and final script.
            if cache_folder.is_symlink() or not cache_folder.is_dir():
                raise UpstreamReuseError("Source-bound narration cache missing")
            if {x.name for x in cache_folder.iterdir()} != set(manifest):
                raise UpstreamReuseError("Narration cache inventory drift")
        for name, digest in manifest.items():
            if (not isinstance(name, str)
                    or not re.fullmatch(r"batch_[0-9]{4}\.json", name)
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise UpstreamReuseError("Unsafe narration response cache manifest")
            if require_cache:
                file = cache_folder / name
                if (file.is_symlink() or not file.is_file()
                        or _sha(file) != digest):
                    raise UpstreamReuseError("Narration cache digest mismatch")
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
    # Importability is per stage, not all-or-nothing. An updated independent
    # scientific reviewer invalidates its OLD receipt (as it should), but
    # must not invalidate independently reverified source PDFs and slide
    # artwork when that science result will be freshly regenerated anyway.
    if any(not completed.get(name) for name in FOUR_UPSTREAM):
        return None
    if not (stage / "source.pdf").is_file() or (stage / "source.pdf").is_symlink():
        return None
    if _sha(stage / "source.pdf") != source_sha:
        return None
    for name in FOUR_UPSTREAM:
        if fingerprints.get(name) != quality.dependency_fingerprint(stage, name):
            return None
        if not stage_valid(stage, name, dest):
            return None
    full_six_valid = all(bool(completed.get(name)) for name in UPSTREAM)
    if full_six_valid:
        for name in UPSTREAM[4:]:
            try:
                if (fingerprints.get(name) !=
                        quality.dependency_fingerprint(stage, name)
                        or not stage_valid(stage, name, dest)):
                    full_six_valid = False
                    break
            except (OSError, ValueError, RuntimeError, KeyError, TypeError):
                full_six_valid = False
                break
    # The old science screen is NEVER adopted if its implementation or
    # transcript fingerprint drifted; four-stage recovery remains possible.
    return (str(completed["slides"]), stage, full_six_valid)


def _copy_evidence(old: Path, target: Path, *, stages=UPSTREAM) -> list[str]:
    """Copy only previously revalidated stages; never import stale audio."""
    copied = []
    voice_rebuild = tuple(stages) == FOUR_UPSTREAM
    for dirname in ALLOW_DIRS:
        if voice_rebuild and dirname == ".microgen_narration_batches":
            continue
        source = old / dirname
        if source.is_dir():
            _safe_filetree(source)
            shutil.copytree(source, target / dirname)
            copied.append(dirname)
    names = set(ALLOW_FILES)
    if voice_rebuild:
        names.difference_update({
            "script.txt", "script_tts.json",
            ".microgen_autonomous_science_qa.json",
        })
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


def _copy_verifiable_narration_response_cache(
    checkpoint_root: Path, target: Path, *,
    source_sha: str, slides_sha: str,
) -> dict | None:
    """Reuse only fully returned, original-source, same-generator model batches.

    A failed narration *stage* must never be resumed as passed. A saved
    successfully returned model response is instead an untrusted candidate
    that the normal generate_batched() rechecks against the exact fresh
    prompt/model/source request key before accepting. This avoids billed
    repeats for already completed batches when ONLY downstream voice
    normalization code changed. No previous script, QA or WAV is imported.
    """
    generation_files = (
        "gen_script_v13.py", "microgen_narration_batch.py",
        "gen_script_prompt_v8_hybrid.md",
    )
    sources = []
    for entry in checkpoint_root.iterdir():
        if (entry.is_symlink() or not entry.is_dir() or entry == target.parent
                or entry.name.startswith(".")):
            continue
        auth = _read_json(entry / OWNER_RECEIPT)
        if (auth is None or auth.get("schema_version") != 1
                or auth.get("publication_authorized") is not False):
            continue
        scope = auth.get("scope", {})
        if (not isinstance(scope, dict) or scope.get("host") != "hp"
                or scope.get("stop_after") != "acceptance"
                or scope.get("source_sha256") != source_sha):
            continue
        old = entry / target.name
        cp = _read_json(old / ".microgen_checkpoint.json")
        cache = old / ".microgen_narration_batches"
        if (cp is None or cp.get("package_commit") != scope.get("code_revision")
                or not cache.is_dir() or cache.is_symlink()
                or not (old / "source.pdf").is_file()
                or not (old / "slides.pdf").is_file()):
            continue
        try:
            if (_sha(old / "source.pdf") != source_sha
                    or _sha(old / "slides.pdf") != slides_sha
                    or any(not (old / name).is_file()
                           or (old / name).is_symlink()
                           or _sha(old / name) != _sha(target / name)
                           for name in generation_files)):
                continue
            names = sorted(cache.iterdir())
            if not 1 <= len(names) <= 40:
                continue
            verified = {}
            for path in names:
                if (not path.is_file() or path.is_symlink()
                        or not re.fullmatch(r"batch_[0-9]{4}\.json", path.name)
                        or path.stat().st_size > 200000):
                    raise UpstreamReuseError("Unsafe cached narration response")
                row = _read_json(path)
                key = row.get("key") if row else None
                responses = row.get("narration") if row else None
                if (not isinstance(key, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", key)
                        or not isinstance(responses, dict)
                        or not 1 <= len(responses) <= 20
                        or any(not isinstance(item, dict)
                               or not isinstance(item.get("narration"), str)
                               or not item["narration"].strip()
                               or not str(item.get("tts_text") or
                                          item["narration"]).strip()
                               for item in responses.values())):
                    raise UpstreamReuseError("Untrusted cached narration row")
                verified[path.name] = _sha(path)
            sources.append((max(x.stat().st_mtime for x in names),
                            entry.name, cache, verified))
        except (OSError, ValueError, TypeError, KeyError, UpstreamReuseError):
            continue
    if not sources:
        return None
    sources.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _, selected, cache, hashes = sources[0]
    dest = target / ".microgen_narration_batches"
    if dest.exists() or dest.is_symlink():
        raise UpstreamReuseError("Narration cache destination already exists")
    dest.mkdir()
    for name, sha in hashes.items():
        shutil.copy2(cache / name, dest / name)
        if _sha(dest / name) != sha:
            raise UpstreamReuseError("Source-bound narration cache drift")
    return {"prior_private_workroot": selected, "file_sha256": hashes,
            "original_response_not_academic_qa": True,
            "requires_exact_prompt_key_revalidation": True}


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
        raise UpstreamReuseError("Ambiguous equally recent source-verified slides")
    _, old, full_six_valid = entries[0]
    # Prior source/figure/slide work is still useful when the *narration*
    # contains known ambiguous math-letter speech. A revised narrator must
    # run again, but re-generating already verified figures/slides is waste.
    # This preflight makes NO provider calls and preserves the prior failure.
    from microgen_reviewed_math_voice import (
        preflight_voice_sidecar, VoiceRiskPreflightError,
    )
    selected_stages = FOUR_UPSTREAM
    if full_six_valid:
        try:
            preflight_voice_sidecar(old)
        except VoiceRiskPreflightError:
            # An old ambiguous/malformed voice sidecar can never be reused.
            # Independently accepted figures and slides remain reusable.
            pass
        else:
            selected_stages = UPSTREAM
    # Use a temporary SOURCE+CURRENTRUNNER stage; no failed-old work or
    # symlinks are promoted before ALL new-code stage validators pass.
    with tempfile.TemporaryDirectory(
        prefix=".microgen-verified-upstream-", dir=work_root
    ) as temp_root:
        stage, cp, checkpoint_path = prepare_stage(
            repo, source_root, Path(temp_root), subchapter, source_wait, commit)
        copied = _copy_evidence(old, stage, stages=selected_stages)
        reuse_cache = None
        if selected_stages == FOUR_UPSTREAM:
            reuse_cache = _copy_verifiable_narration_response_cache(
                root, stage, source_sha=source_sha,
                slides_sha=_sha(old / "slides.pdf"))
        for name in selected_stages:
            if not stage_valid(stage, name, dest):
                raise UpstreamReuseError(
                    f"Current-code source QA failed imported {name}; "
                    "no old acceptance reused")
        summary = {
            "schema_version": 1,
            "status": (SIX_STATUS if selected_stages == UPSTREAM else FOUR_STATUS),
            "source_pdf_sha256": source_sha,
            "origin_stage": str(old),
            "origin_slides_pdf_sha256": _sha(old / "slides.pdf"),
            "source_caption_vector_recovery_receipt_sha256": (
                _sha(stage / ".microgen_source_caption_vector_recovery.json")
                if (stage / ".microgen_source_caption_vector_recovery.json").is_file()
                else None),
            "current_code_revision": commit,
            "stages": list(selected_stages),
            "full_previous_science_verification_current_code":
                bool(full_six_valid and selected_stages == UPSTREAM),
            "copied_items": copied,
            "source_bound_narration_response_cache": reuse_cache,
            "new_audio_reused": False,
            "new_model_requests": False,
            "publication_allowed": False,
        }
        (stage / RECEIPT).write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        for name in selected_stages:
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
        "stages": list(selected_stages),
        "audio_reused": False,
        "cached_model_responses_reused": (
            len(reuse_cache["file_sha256"]) if reuse_cache else 0),
    }
