"""Ordered Gemini API-key discovery and failover for MicroGen_AI."""
from __future__ import annotations

import hashlib
import os
import random
import threading
import time
from typing import Callable, TypeVar

from gemini_lane import (
    GeminiBillingError,
    assert_gemini_available,
    is_billing_gemini_error,
    is_transient_gemini_error,
    trip_billing_circuit,
)

T = TypeVar("T")

# Process-local only: never persist API-key material or health state to Drive.
# This avoids retrying an unavailable key on every page within one worker.
_KEY_COOLDOWN_UNTIL: dict[str, float] = {}
_KEY_COOLDOWN_LOCK = threading.Lock()


def _key_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _available_key_order(keys: list[str]) -> list[tuple[int, str]]:
    indexed = list(enumerate(keys, start=1))
    if len(indexed) < 2:
        return indexed
    now = time.monotonic()
    with _KEY_COOLDOWN_LOCK:
        for name, until in list(_KEY_COOLDOWN_UNTIL.items()):
            if until <= now:
                _KEY_COOLDOWN_UNTIL.pop(name, None)
        available = [(index, key) for index, key in indexed
                     if _key_fingerprint(key) not in _KEY_COOLDOWN_UNTIL]
    # All keys cooling? Retry all rather than causing a false total outage.
    return available or indexed


def _remember_unavailable_key(key: str, exc: BaseException, total_keys: int) -> None:
    if total_keys < 2 or is_billing_gemini_error(exc):
        return  # Preserve the full all-keys billing circuit semantics.
    code = _error_code(exc)
    message = _error_text(exc)
    auth_markers = ("INVALID API KEY", "API KEY NOT VALID", "UNAUTHENTICATED",
                    "PERMISSION_DENIED", "QUOTA_EXCEEDED", "QUOTA_EXHAUSTED")
    if not (code in (401, 403, 429)
            or (code == 400 and "API KEY" in message)
            or any(marker in message for marker in auth_markers)):
        return
    seconds = max(0.0, min(3600.0, _env_float(
        "MICROGEN_GEMINI_KEY_COOLDOWN_SECONDS", 120.0)))
    if seconds == 0:
        return
    with _KEY_COOLDOWN_LOCK:
        _KEY_COOLDOWN_UNTIL[_key_fingerprint(key)] = time.monotonic() + seconds


def _error_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}".upper()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def _import_sdk():
    """Lazy SDK import so offline checks remain usable on damaged environments."""
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise RuntimeError(
            "The Google Gemini SDK cannot be imported in this Python environment. "
            "Run 'python -c \"import google.genai\"' in the chosen environment; "
            "repair/reinstall google-genai, pydantic and corrupted package metadata "
            "before running paid generation."
        ) from exc
    return genai, types


def create_gemini_client(api_key: str):
    """Create a Gemini client whose timeout/retries are owned by MicroGen."""
    genai, types = _import_sdk()
    timeout_ms = max(1_000, _env_int("MICROGEN_GEMINI_REQUEST_TIMEOUT_MS", 120_000))
    sdk_attempts = max(1, _env_int("MICROGEN_GEMINI_SDK_RETRY_ATTEMPTS", 1))
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=sdk_attempts),
        ),
    )


def get_gemini_api_keys() -> list[str]:
    """Return Gemini keys in deterministic priority order without duplicates."""
    prefix = "GEMINI_API_KEY_"
    indexed: list[tuple[int, str]] = []
    for name, value in os.environ.items():
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix):]
        if suffix.isdigit() and value.strip():
            indexed.append((int(suffix), value.strip()))

    values = [value for _, value in sorted(indexed)]
    csv = os.environ.get("GEMINI_API_KEYS", "").strip()
    if csv:
        values.extend(part.strip() for part in csv.split(",") if part.strip())
    legacy = os.environ.get("GEMINI_API_KEY", "").strip()
    if legacy:
        values.append(legacy)

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def is_key_failover_error(exc: BaseException) -> bool:
    """Return True when another configured key should be tried immediately."""
    if is_billing_gemini_error(exc):
        return True
    code = _error_code(exc)
    text = _error_text(exc)
    if code in {401, 403, 429}:
        return True
    if code == 400 and ("API KEY" in text or "INVALID_ARGUMENT" in text):
        return True
    markers = (
        "API KEY NOT VALID",
        "INVALID API KEY",
        "UNAUTHENTICATED",
        "PERMISSION_DENIED",
        "PERMISSION DENIED",
        "QUOTA_EXCEEDED",
        "QUOTA EXCEEDED",
        "QUOTA_EXHAUSTED",
    )
    return any(marker in text for marker in markers)


def call_with_client_failover(
    client_factory: Callable[[str], object],
    operation_for_client: Callable[[object], T],
    *,
    label: str = "Gemini request",
    max_retries: int | None = None,
) -> T:
    """Run a Gemini operation while keeping each SDK client alive for the full request."""
    def operation_for_key(api_key: str) -> T:
        client = client_factory(api_key)
        try:
            return operation_for_client(client)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    return call_with_key_failover(
        operation_for_key,
        label=label,
        max_retries=max_retries,
    )


def call_with_key_failover(
    operation_for_key: Callable[[str], T],
    *,
    label: str = "Gemini request",
    max_retries: int | None = None,
) -> T:
    """Run one Gemini operation using the configured key pool in priority order."""
    assert_gemini_available()
    keys = get_gemini_api_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API key configured. Set GEMINI_API_KEY_1 and optionally "
            "GEMINI_API_KEY_2, GEMINI_API_KEY_3, or the legacy GEMINI_API_KEY."
        )

    retries = _env_int("MICROGEN_GEMINI_MAX_RETRIES", 6) if max_retries is None else max_retries
    base = _env_float("MICROGEN_GEMINI_BACKOFF_BASE_SECONDS", 15.0)
    cap = _env_float("MICROGEN_GEMINI_BACKOFF_MAX_SECONDS", 180.0)
    transient_retries_per_key = max(
        1,
        _env_int("MICROGEN_GEMINI_TRANSIENT_RETRIES_PER_KEY", 2),
    )
    last_key_error: BaseException | None = None
    billing_failed_keys = 0

    ordered_keys = _available_key_order(keys)
    for sequence_index, (key_index, key) in enumerate(ordered_keys):
        next_key_index = (ordered_keys[sequence_index + 1][0]
                          if sequence_index + 1 < len(ordered_keys) else None)
        transient_failures = 0
        for attempt in range(retries + 1):
            try:
                return operation_for_key(key)
            except Exception as exc:
                if is_key_failover_error(exc):
                    last_key_error = exc
                    _remember_unavailable_key(key, exc, len(keys))
                    if is_billing_gemini_error(exc):
                        billing_failed_keys += 1
                    if next_key_index is not None:
                        print(
                            f"[Gemini keys] {label}: key #{key_index} unavailable "
                            f"({type(exc).__name__}); falling back to key #{next_key_index}",
                            flush=True,
                        )
                    break

                if not is_transient_gemini_error(exc):
                    raise

                transient_failures += 1

                if (
                    next_key_index is not None
                    and transient_failures >= transient_retries_per_key
                ):
                    print(
                        f"[Gemini keys] {label}: key #{key_index} had "
                        f"{transient_failures} consecutive transient failures "
                        f"({type(exc).__name__}: {exc}); rotating to key #{next_key_index}",
                        flush=True,
                    )
                    break

                if attempt >= retries:
                    raise

                delay = min(cap, base * (2 ** attempt))
                delay += random.uniform(0.0, min(5.0, max(1.0, delay * 0.15)))
                print(
                    f"[Gemini retry] {label} transient failure on key #{key_index} "
                    f"({type(exc).__name__}: {exc}); retry {attempt + 1}/{retries} "
                    f"in {delay:.1f}s",
                    flush=True,
                )
                time.sleep(delay)

    if (
        last_key_error is not None
        and is_billing_gemini_error(last_key_error)
        and billing_failed_keys == len(keys)
    ):
        trip_billing_circuit(last_key_error, label=f"{label} (all configured keys)")
        raise GeminiBillingError(
            f"{label} stopped because every configured Gemini key reported "
            f"billing/prepayment failure: {last_key_error}"
        ) from last_key_error
    if last_key_error is not None:
        raise RuntimeError(
            f"{label} failed because all {len(keys)} configured Gemini API keys "
            f"were unavailable: {last_key_error}"
        ) from last_key_error
    raise RuntimeError(f"{label} failed without a usable Gemini API key")
