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
    s=str(exc).upper()
    if any(marker in s for marker in PERMANENT):
        return False
    if any(marker in s for marker in TRANSIENT):
        return True
    return any(marker in s for marker in (" 408"," 429"," 500"," 502"," 503"," 504",
                                          "408 ","429 ","500 ","502 ","503 ","504 "))
class AudioRecognitionUnavailable(RuntimeError):
    pass

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
                    f"Acoustic recognizer unavailable after {i+1} attempt(s) "
                    f"({type(exc).__name__})") from None
            sleep((1,3)[i])
    raise AssertionError("Unreachable retry loop")
