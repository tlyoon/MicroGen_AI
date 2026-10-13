"""Adaptive, resume-safe Gemini narration batches.

Avoid a 54-slide/one-request timeout by dividing the work into bounded groups.
Every batch is keyed to its complete source, slide content, model and prompt.
No shared-state globals or provider imports, so offline tests are trivial.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Callable


class NarrationBatchError(RuntimeError):
    pass


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")


def _check(slides: list[dict], response: dict) -> None:
    wanted = [x["id"] for x in slides]
    if not isinstance(response, dict) or set(response) != set(wanted):
        raise NarrationBatchError(
            f"Batch ID mismatch: expected {wanted}, got {list(response) if isinstance(response, dict) else type(response)}"
        )
    for sid in wanted:
        item = response[sid]
        if not isinstance(item, dict):
            raise NarrationBatchError(f"Not a narration object: {sid}")
        if not str(item.get("narration") or "").strip():
            raise NarrationBatchError(f"Empty generated narration: {sid}")
        if not str(item.get("tts_text") or item.get("narration") or "").strip():
            raise NarrationBatchError(f"Empty voice-ready narration: {sid}")


def generate_batched(
    slides: list[dict],
    source_blocks,
    generate: Callable[[list[dict], object], dict],
    *,
    cache_dir: Path = Path(".microgen_narration_batches"),
    model: str,
    prompt_hash: str = "",
    batch_size: int | None = None,
) -> dict:
    """Generate exact, source-ordered slide narration with durable checkpoints.

    Each accepted JSON batch survives 503/504 failures and can be reused when
    the inputs are byte-identical. Earlier batches are never regenerated merely
    because a later batch failed. No tokens or narration are silently dropped.
    """
    if batch_size is None:
        raw = os.environ.get("MICROGEN_NARRATION_BATCH_SIZE", "8")
        try:
            batch_size = int(raw)
        except ValueError as exc:
            raise NarrationBatchError("MICROGEN_NARRATION_BATCH_SIZE must be an integer") from exc
    if not 1 <= batch_size <= 20:
        raise NarrationBatchError("Batch size must be between 1 and 20")
    if not slides:
        raise NarrationBatchError("Slide inventory cannot be empty")
    expected = [x["id"] for x in slides]
    if any(not isinstance(sid, str) or not sid for sid in expected) or len(set(expected)) != len(expected):
        raise NarrationBatchError("Slide IDs must be unique, nonempty strings")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    source_digest = hashlib.sha256(_canonical(source_blocks)).hexdigest()
    for start in range(0, len(slides), batch_size):
        batch = slides[start:start + batch_size]
        sig = {
            "schema": 2, "source_sha256": source_digest,
            "slides": batch, "model": model,
            "prompt_sha256": prompt_hash, "size": batch_size,
        }
        key = hashlib.sha256(_canonical(sig)).hexdigest()
        cache_file = cache_dir / f"batch_{start:04d}.json"
        accepted = None
        if cache_file.is_file():
            try:
                saved = json.loads(cache_file.read_text(encoding="utf-8"))
                if saved.get("key") == key:
                    _check(batch, saved["narration"])
                    accepted = saved["narration"]
            except (OSError, ValueError, KeyError, TypeError, NarrationBatchError):
                accepted = None
        if accepted is None:
            print(f"[narration] generating slides {start+1}-{start+len(batch)} "
                  f"of {len(slides)}", flush=True)
            accepted = generate(batch, source_blocks)
            _check(batch, accepted)
            payload = {"key": key, "narration": accepted}
            pending = cache_file.with_suffix(".json.tmp")
            pending.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                               encoding="utf-8")
            pending.replace(cache_file)
        else:
            print(f"[narration] resumed verified batch {start+1}-{start+len(batch)}",
                  flush=True)
        result.update(accepted)
    if set(result) != set(expected):
        raise NarrationBatchError("Narration output has omitted or extra slide IDs")
    return result
