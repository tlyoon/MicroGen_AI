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


def _read_timeout(exc: BaseException) -> bool:
    """Only known transport read-timeouts qualify for a smaller request."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if type(exc).__name__ in {"ReadTimeout"}:
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def _generate_with_bounded_split(
    slides: list[dict], source_blocks, generate, *, cache_dir: Path,
    start: int, parent_key: str, prompt_fingerprint,
) -> dict:
    """One split for a timed-out large request, with SHA-bound child checkpoints.

    A durable marker prevents retrying the same oversized request after restart.
    No recursive splitting, no bypass of the caller's provider authorization.
    """
    marker = cache_dir / f"batch_{start:04d}.split.json"
    split = False
    if marker.is_file():
        try:
            split = json.loads(marker.read_text(encoding="utf-8")).get("key") == parent_key
        except (ValueError, OSError, AttributeError):
            split = False
    if not split:
        try:
            return generate(slides, source_blocks)
        except Exception as exc:
            if len(slides) < 2 or not _read_timeout(exc):
                raise
            marker_tmp = marker.with_suffix(".json.tmp")
            marker_tmp.write_text(json.dumps({"key": parent_key, "reason": "ReadTimeout"}),
                                  encoding="utf-8")
            marker_tmp.replace(marker)
            print(f"[narration] read timeout: splitting {len(slides)} slides once",
                  flush=True)
    midpoint = len(slides) // 2
    result = {}
    for offset, part in ((0, slides[:midpoint]), (midpoint, slides[midpoint:])):
        prompt = prompt_fingerprint(part) if prompt_fingerprint is not None else ""
        if prompt_fingerprint is not None and (
            not isinstance(prompt, str) or not prompt.strip()
        ):
            raise NarrationBatchError("Empty split narration request fingerprint")
        key = hashlib.sha256(_canonical({
            "parent": parent_key, "offset": offset, "slides": part, "prompt": prompt,
        })).hexdigest()
        path = cache_dir / f"batch_{start:04d}_split_{offset:04d}.json"
        accepted = None
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("key") == key:
                    _check(part, payload["narration"])
                    accepted = payload["narration"]
            except (OSError, ValueError, KeyError, TypeError, NarrationBatchError):
                pass
        if accepted is None:
            accepted = generate(part, source_blocks)
            _check(part, accepted)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"key": key, "narration": accepted},
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        result.update(accepted)
    _check(slides, result)
    return result


def generate_batched(
    slides: list[dict],
    source_blocks,
    generate: Callable[[list[dict], object], dict],
    *,
    cache_dir: Path = Path(".microgen_narration_batches"),
    model: str,
    prompt_hash: str = "",
    batch_size: int | None = None,
    prompt_fingerprint: Callable[[list[dict]], str] | None = None,
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
        # The request's *actual* composed prompt, not merely a separate
        # prompt-template filename, controls cache identity. Otherwise
        # instructions embedded in the generator can change while an older
        # response is silently reused. Callback runs before cache lookup.
        active_prompt = (prompt_fingerprint(batch)
                         if prompt_fingerprint is not None else prompt_hash)
        if prompt_fingerprint is not None and (
                not isinstance(active_prompt, str) or not active_prompt.strip()):
            raise NarrationBatchError("Empty narration request fingerprint")
        sig = {
            "schema": 3 if prompt_fingerprint is not None else 2,
            "source_sha256": source_digest,
            "slides": batch, "model": model,
            "prompt_sha256": active_prompt, "size": batch_size,
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
            accepted = _generate_with_bounded_split(
                batch, source_blocks, generate, cache_dir=cache_dir,
                start=start, parent_key=key, prompt_fingerprint=prompt_fingerprint,
            )
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
