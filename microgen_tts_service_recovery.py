"""Bounded retry policy for audio understanding, without secret leakage.

Transient transport/rate failures can recover. Auth failures, nonexistent
models and exhausted hard quota cannot. A previous failure is never treated
as a successful acoustic screen. All retries are bounded.
"""
from __future__ import annotations
from collections.abc import Callable
from typing import TypeVar
T=TypeVar("T")

PERMANENT=(
    "QUOTA EXCEEDED", "LIMIT: 0", "RESOURCE_EXHAUSTED: QUOTA",
    "INVALID API KEY","API_KEY_INVALID","PERMISSION_DENIED",
    "MODEL NOT FOUND","NOT_FOUND","INVALID_ARGUMENT",
    "UNAUTHENTICATED","BILLING DISABLED",
)
TRANSIENT=(
    "RATE LIMIT","TOO MANY REQUESTS","RESOURCE_EXHAUSTED: RATE",
    "UNAVAILABLE","DEADLINE_EXCEEDED","SERVICE UNAVAILABLE",
    "TIMEOUT","TIMED OUT","CONNECTION RESET","CONNECTION ERROR",
    "INTERNAL SERVER ERROR","BACKEND ERROR",
)

def transient_service_error(exc:Exception)->bool:
    """Conservative classification; unknown errors are not retried."""
    if isinstance(exc, AudioSchemaCompatibilityRetry):
        return True
    s=str(exc).upper()
    if any(marker in s for marker in PERMANENT):
        return False
    if any(marker in s for marker in TRANSIENT):
        return True
    return any(marker in s for marker in (" 408"," 429"," 500"," 502"," 503"," 504",
                                          "408 ","429 ","500 ","502 ","503 ","504 "))
class AudioRecognitionUnavailable(RuntimeError):
    """Safe structured failure: never persist keys, URLs or response content."""
    def __init__(self, *, failure_kind: str, http_status: int | None,
                 attempts: int, exception_class: str):
        self.failure_kind=failure_kind
        self.http_status=http_status
        self.attempts=attempts
        self.exception_class=exception_class
        super().__init__(
            f"Acoustic recognizer failed kind={failure_kind} "
            f"http_status={http_status if http_status is not None else 'unknown'} "
            f"after {attempts} attempt(s) ({exception_class})"
        )


class AudioSchemaCompatibilityRetry(RuntimeError):
    """One bounded request-mode downgrade, only for a verified JSON schema 400."""


def safe_http_status(exc: BaseException) -> int | None:
    """Numeric status only; never log provider messages or secrets."""
    code=getattr(exc,"code",None)
    if callable(code):
        try:
            code=code()
        except Exception:
            code=None
    try:
        code=int(code)
    except (ValueError,TypeError):
        code=None
    if code is not None:
        return code if 100<=code<=599 else None
    import re
    match=re.search(r"(?<![0-9])(?:400|401|403|404|408|429|500|502|503|504)(?![0-9])",
                    str(exc)[:250])
    return int(match.group()) if match else None


def failure_kind(exc: BaseException) -> str:
    if isinstance(exc,AudioSchemaCompatibilityRetry):
        return "SCHEMA_COMPATIBILITY_RETRY"
    code=safe_http_status(exc)
    body=str(exc).upper()[:500]
    if code in (401,403) or any(x in body for x in
                              ("UNAUTHENTICATED","PERMISSION_DENIED","INVALID API KEY")):
        return "AUTHORIZATION"
    if ("QUOTA EXCEEDED" in body or "LIMIT: 0" in body
            or "RESOURCE_EXHAUSTED: QUOTA" in body):
        return "HARD_QUOTA"
    if code==404 or "MODEL NOT FOUND" in body:
        return "MODEL_UNAVAILABLE"
    if code==400 or "INVALID_ARGUMENT" in body:
        return "INVALID_REQUEST"
    if transient_service_error(exc):
        return "TRANSIENT_PROVIDER"
    if isinstance(exc,ValueError):
        return "INVALID_TRANSCRIPT"
    return "UNKNOWN_FAILURE"


def run_bounded_recognition(fn:Callable[[],T],sleep:Callable[[float],None],
                            *,max_attempts:int=3)->T:
    if type(max_attempts) is not int or not 1<=max_attempts<=3:
        raise ValueError("Recognition retry limit must be 1-3")
    for i in range(max_attempts):
        try:
            result=fn()
            if not isinstance(result,str) or not result.strip():
                raise ValueError("Empty acoustic transcript")
            return result
        except Exception as exc:
            if i==max_attempts-1 or not transient_service_error(exc):
                raise AudioRecognitionUnavailable(
                    failure_kind=failure_kind(exc),
                    http_status=safe_http_status(exc),
                    attempts=i+1,exception_class=type(exc).__name__) from None
            sleep((1,3)[i])
    raise AssertionError("Unreachable retry loop")
