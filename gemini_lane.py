"""Cross-process / cross-PC coordination and retry policy for Gemini API stages.

The shared lane serializes Gemini requests across participating computers. It
also maintains a shared circuit breaker so non-retryable billing failures stop
all workers quickly instead of consuming the retry budget on every machine.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, TypeVar

T = TypeVar("T")

_TRANSIENT_MARKERS = (
    "429", "RATE_LIMIT", "RATE LIMIT", "TOO MANY REQUESTS",
    "QUOTA_EXHAUSTED", "QUOTA_EXCEEDED", "QUOTA EXCEEDED",
    "500", "502", "503", "504", "UNAVAILABLE",
    "DEADLINE_EXCEEDED", "INTERNAL", "OVERLOADED", "CAPACITY",
    "TIMEOUT", "TIMED OUT", "READTIMEOUT", "CONNECTTIMEOUT",
)
_BILLING_MARKERS = (
    "PREPAYMENT CREDITS ARE DEPLETED",
    "PREPAYMENT CREDIT",
    "MANAGE YOUR PROJECT AND BILLING",
    "BILLING#PREPAY",
    "BILLING ACCOUNT",
)


class GeminiBillingError(RuntimeError):
    """Gemini cannot proceed until project billing/credit is restored."""


class GeminiCircuitOpen(RuntimeError):
    """The shared Gemini circuit breaker is currently open."""


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    return float(value) if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:80]


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
    return f"{type(exc).__name__}: {exc} {_error_code(exc)}".upper()


def is_billing_gemini_error(exc: BaseException) -> bool:
    code = _error_code(exc)
    text = _error_text(exc)
    return code == 402 or any(marker in text for marker in _BILLING_MARKERS)


def is_transient_gemini_error(exc: BaseException) -> bool:
    if is_billing_gemini_error(exc):
        return False
    code = _error_code(exc)
    if code in {408, 429, 500, 502, 503, 504}:
        return True
    text = _error_text(exc)
    return "RESOURCE_EXHAUSTED" in text or any(marker in text for marker in _TRANSIENT_MARKERS)


def _lane_root() -> Path | None:
    raw = os.environ.get("MICROGEN_GEMINI_LANE_DIR", "").strip()
    return Path(raw).expanduser() if raw else None


def _circuit_path() -> Path | None:
    root = _lane_root()
    return root / "circuit_breaker.json" if root else None


def circuit_status() -> dict[str, object] | None:
    path = _circuit_path()
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def circuit_is_open() -> tuple[bool, dict[str, object] | None]:
    data = circuit_status()
    if not data:
        return False, None
    retry_after = float(data.get("retry_after_epoch", 0) or 0)
    if retry_after > time.time():
        return True, data
    # The retry window has elapsed. Remove the breaker so the first serialized
    # request can probe the service again. If billing is still depleted it will
    # immediately recreate the breaker.
    path = _circuit_path()
    if path is not None:
        try:
            history = path.parent / "history"
            history.mkdir(parents=True, exist_ok=True)
            path.replace(history / f"circuit_breaker.expired.{_utc_stamp()}.json")
        except OSError:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    return False, data


def trip_billing_circuit(exc: BaseException, *, label: str = "Gemini request") -> None:
    path = _circuit_path()
    if path is None:
        return
    retry_seconds = _env_float("MICROGEN_GEMINI_BILLING_RECHECK_SECONDS", 1800.0)
    payload = {
        "type": "billing",
        "label": label,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "retry_after_epoch": time.time() + retry_seconds,
        "retry_after_seconds": retry_seconds,
        "error_type": type(exc).__name__,
        "error": str(exc)[:2000],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
        print(
            f"[Gemini circuit] OPEN billing blocker; suppressing Gemini calls for "
            f"{retry_seconds:.0f}s across participating workers",
            flush=True,
        )
    except OSError:
        pass


def clear_circuit() -> bool:
    path = _circuit_path()
    if path is None or not path.exists():
        return False
    try:
        history = path.parent / "history"
        history.mkdir(parents=True, exist_ok=True)
        path.replace(history / f"circuit_breaker.cleared.{_utc_stamp()}.json")
        return True
    except OSError:
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            return False


def assert_gemini_available() -> None:
    opened, data = circuit_is_open()
    if not opened:
        return
    retry_after = float((data or {}).get("retry_after_epoch", 0) or 0)
    wait = max(0, retry_after - time.time())
    reason = (data or {}).get("type", "unknown")
    raise GeminiCircuitOpen(
        f"Shared Gemini circuit is open ({reason}); next automatic probe in about {wait:.0f}s."
    )


def call_with_retry(
    operation: Callable[[], T],
    *,
    label: str = "Gemini request",
    max_retries: int | None = None,
) -> T:
    """Run one Gemini request with retry for transient service errors only.

    Billing/prepayment failures are never retried. They trip the shared circuit
    breaker so other workers stop quickly instead of duplicating doomed calls.
    """
    assert_gemini_available()
    retries = _env_int("MICROGEN_GEMINI_MAX_RETRIES", 6) if max_retries is None else max_retries
    base = _env_float("MICROGEN_GEMINI_BACKOFF_BASE_SECONDS", 15.0)
    cap = _env_float("MICROGEN_GEMINI_BACKOFF_MAX_SECONDS", 180.0)
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as exc:
            if is_billing_gemini_error(exc):
                trip_billing_circuit(exc, label=label)
                raise GeminiBillingError(
                    f"{label} stopped because Gemini billing/prepayment credit is unavailable: {exc}"
                ) from exc
            if attempt >= retries or not is_transient_gemini_error(exc):
                raise
            delay = min(cap, base * (2 ** attempt))
            delay += random.uniform(0.0, min(5.0, max(1.0, delay * 0.15)))
            print(
                f"[Gemini retry] {label} transient failure ({type(exc).__name__}: {exc}); "
                f"retry {attempt + 1}/{retries} in {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(f"{label} exhausted retries")


class GeminiLane:
    def __init__(self, stage: str, model: str = "", cooldown: float | None = None) -> None:
        raw = os.environ.get("MICROGEN_GEMINI_LANE_DIR", "").strip()
        self.enabled = bool(raw)
        self.root = Path(raw).expanduser() if raw else None
        self.stage = stage
        self.model = model
        self.host = socket.gethostname()
        self.pid = os.getpid()
        self.token = uuid.uuid4().hex
        self.ticket: Path | None = None
        self._stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self.settle = _env_float("MICROGEN_GEMINI_LANE_SETTLE_SECONDS", 20.0)
        self.claim_grace = _env_float("MICROGEN_GEMINI_LANE_CLAIM_GRACE_SECONDS", 8.0)
        self.poll = _env_float("MICROGEN_GEMINI_LANE_POLL_SECONDS", 5.0)
        self.stale = _env_float("MICROGEN_GEMINI_LANE_STALE_SECONDS", 3600.0)
        self.heartbeat = _env_float("MICROGEN_GEMINI_LANE_HEARTBEAT_SECONDS", 30.0)
        self.cooldown = (
            _env_float("MICROGEN_GEMINI_LANE_COOLDOWN_SECONDS", 10.0)
            if cooldown is None else max(0.0, float(cooldown))
        )

    @property
    def queue_dir(self) -> Path:
        assert self.root is not None
        return self.root / "queue"

    @property
    def history_dir(self) -> Path:
        assert self.root is not None
        return self.root / "history"

    def _ticket_payload(self) -> dict[str, object]:
        return {
            "token": self.token,
            "host": self.host,
            "pid": self.pid,
            "stage": self.stage,
            "model": self.model,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _write_ticket(self) -> None:
        mount_wait = _env_float("MICROGEN_GEMINI_LANE_MOUNT_WAIT_SECONDS", 300.0)
        deadline = time.time() + mount_wait
        while True:
            try:
                self.queue_dir.mkdir(parents=True, exist_ok=True)
                self.history_dir.mkdir(parents=True, exist_ok=True)
                break
            except OSError as exc:
                if time.time() >= deadline:
                    raise RuntimeError(
                        f"Gemini lane storage unavailable for {mount_wait:.0f}s: {self.root}"
                    ) from exc
                print(f"[Gemini lane] shared drive unavailable; waiting for {self.root}", flush=True)
                time.sleep(min(10.0, max(1.0, self.poll)))
        name = f"{_utc_stamp()}__{_safe(self.host)}__{self.pid}__{self.token}.ticket.json"
        self.ticket = self.queue_dir / name
        self.ticket.write_text(json.dumps(self._ticket_payload(), indent=2), encoding="utf-8")

    def _tickets(self) -> list[Path]:
        try:
            return sorted(p for p in self.queue_dir.glob("*.ticket.json") if p.is_file())
        except OSError:
            return []

    def _remove_stale(self) -> None:
        now = time.time()
        for path in self._tickets():
            if self.ticket is not None and path == self.ticket:
                continue
            try:
                if now - path.stat().st_mtime > self.stale:
                    stale_name = f"{path.name}.stale.{_utc_stamp()}"
                    try:
                        path.replace(self.history_dir / stale_name)
                    except OSError:
                        path.unlink(missing_ok=True)
                    print(f"[Gemini lane] removed stale ticket {path.name}", flush=True)
            except OSError:
                continue

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.heartbeat):
            try:
                if self.ticket is not None and self.ticket.exists():
                    os.utime(self.ticket, None)
            except OSError:
                pass

    def acquire(self) -> None:
        if not self.enabled:
            assert_gemini_available()
            return
        assert_gemini_available()
        self._write_ticket()
        assert self.ticket is not None
        print(
            f"[Gemini lane] queued stage={self.stage} host={self.host} "
            f"ticket={self.ticket.name}; settling {self.settle:.0f}s",
            flush=True,
        )
        time.sleep(self.settle)
        last_report = 0.0
        storage_wait = _env_float("MICROGEN_GEMINI_LANE_MOUNT_WAIT_SECONDS", 300.0)
        missing_since: float | None = None
        while True:
            # A circuit can be tripped while this worker is waiting in the queue.
            opened, data = circuit_is_open()
            if opened:
                try:
                    self.ticket.unlink(missing_ok=True)
                except OSError:
                    pass
                retry_after = float((data or {}).get("retry_after_epoch", 0) or 0)
                raise GeminiCircuitOpen(
                    f"Shared Gemini circuit opened while queued; next probe in "
                    f"{max(0, retry_after-time.time()):.0f}s."
                )
            self._remove_stale()
            tickets = self._tickets()
            names = [p.name for p in tickets]
            if self.ticket.name not in names:
                if missing_since is None:
                    missing_since = time.time()
                if time.time() - missing_since <= storage_wait:
                    if time.time() - last_report >= 30.0:
                        print("[Gemini lane] ticket/storage temporarily unavailable; waiting for shared drive", flush=True)
                        last_report = time.time()
                    time.sleep(self.poll)
                    continue
                raise RuntimeError(
                    f"Gemini lane ticket unavailable for {storage_wait:.0f}s: {self.ticket}"
                )
            missing_since = None
            if tickets and tickets[0].name == self.ticket.name:
                time.sleep(self.claim_grace)
                self._remove_stale()
                tickets2 = self._tickets()
                if tickets2 and tickets2[0].name == self.ticket.name:
                    break
            now = time.time()
            if now - last_report >= 30.0:
                head = tickets[0].name if tickets else "<none>"
                print(
                    f"[Gemini lane] waiting stage={self.stage} host={self.host}; "
                    f"queue={len(tickets)} head={head}",
                    flush=True,
                )
                last_report = now
            time.sleep(self.poll)
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"gemini-lane-heartbeat-{self.pid}",
            daemon=True,
        )
        self._heartbeat_thread.start()
        print(
            f"[Gemini lane] ACQUIRED stage={self.stage} host={self.host} model={self.model}",
            flush=True,
        )

    def release(self, exc: BaseException | None = None) -> None:
        if not self.enabled:
            return
        # Do not waste cooldown time after a billing/circuit failure.
        if self.cooldown > 0 and not isinstance(exc, (GeminiBillingError, GeminiCircuitOpen)):
            print(
                f"[Gemini lane] cooldown {self.cooldown:.0f}s before release "
                f"stage={self.stage} host={self.host}",
                flush=True,
            )
            time.sleep(self.cooldown)
        self._stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
        if self.ticket is None:
            return
        payload = self._ticket_payload()
        payload["released_utc"] = datetime.now(timezone.utc).isoformat()
        payload["result"] = "error" if exc is not None else "ok"
        payload["error_type"] = type(exc).__name__ if exc is not None else None
        try:
            hist = self.history_dir / f"{self.ticket.stem}.done.json"
            hist.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass
        try:
            self.ticket.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"[Gemini lane] RELEASED stage={self.stage} host={self.host}", flush=True)


@contextlib.contextmanager
def gemini_lane(stage: str, model: str = "", cooldown: float | None = None) -> Iterator[None]:
    lane = GeminiLane(stage=stage, model=model, cooldown=cooldown)
    if not lane.enabled:
        assert_gemini_available()
        yield
        return
    lane.acquire()
    caught: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        caught = exc
        raise
    finally:
        lane.release(caught)


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Inspect or clear the shared MicroGen Gemini circuit breaker.")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--clear-circuit", action="store_true")
    args = ap.parse_args()
    if args.clear_circuit:
        print("cleared" if clear_circuit() else "no circuit marker present")
    if args.status or not args.clear_circuit:
        data = circuit_status()
        print(json.dumps(data, indent=2) if data else "circuit closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
