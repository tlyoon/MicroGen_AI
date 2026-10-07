"""Ordered Gemini API-key discovery and failover for MicroGen_AI."""
from __future__ import annotations

import os
import random
import time
from typing import Callable, TypeVar

from google import genai
from google.genai import types

from gemini_lane import (
    GeminiBillingError,
    assert_gemini_available,
    is_billing_gemini_error,
    is_transient_gemini_error,
    trip_billing_circuit,
)

T = TypeVar("T")


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


def create_gemini_client(api_key: str):
    """Create a Gemini client whose timeout/retries are owned by MicroGen."""
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

    for key_index, key in enumerate(keys, start=1):
        transient_failures = 0
        for attempt in range(retries + 1):
            try:
                return operation_for_key(key)
            except Exception as exc:
                if is_key_failover_error(exc):
                    last_key_error = exc
                    if is_billing_gemini_error(exc):
                        billing_failed_keys += 1
                    if key_index < len(keys):
                        print(
                            f"[Gemini keys] {label}: key #{key_index} unavailable "
                            f"({type(exc).__name__}); falling back to key #{key_index + 1}",
                            flush=True,
                        )
                    break

                if not is_transient_gemini_error(exc):
                    raise

                transient_failures += 1

                if (
                    key_index < len(keys)
                    and transient_failures >= transient_retries_per_key
                ):
                    print(
                        f"[Gemini keys] {label}: key #{key_index} had "
                        f"{transient_failures} consecutive transient failures "
                        f"({type(exc).__name__}: {exc}); rotating to key #{key_index + 1}",
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
