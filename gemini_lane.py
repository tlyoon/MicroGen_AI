"""Cross-process / cross-PC coordination for Gemini API stages.

MicroGen_AI can use several computers against one Gemini project. Gemini
quotas/capacity are project-scoped, so parallel long-running stages can cause
429/503 errors. This module provides a cooperative FIFO lane backed by a
shared directory plus conservative retry/backoff.

The lane is disabled unless MICROGEN_GEMINI_LANE_DIR is set.
"""
from __future__ import annotations
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
    "429","RESOURCE_EXHAUSTED","RATE_LIMIT","RATE LIMIT","TOO MANY REQUESTS",
    "QUOTA_EXHAUSTED","QUOTA_EXCEEDED","QUOTA EXCEEDED","500","502","503","504","UNAVAILABLE",
    "DEADLINE_EXCEEDED","INTERNAL","OVERLOADED","CAPACITY",
)

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

def is_transient_gemini_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    if code in {408, 429, 500, 502, 503, 504}:
        return True
    text = f"{type(exc).__name__}: {exc} {code}".upper()
    return any(marker in text for marker in _TRANSIENT_MARKERS)

def call_with_retry(operation: Callable[[], T], *, label: str = "Gemini request", max_retries: int | None = None) -> T:
    retries = _env_int("MICROGEN_GEMINI_MAX_RETRIES", 6) if max_retries is None else max_retries
    base = _env_float("MICROGEN_GEMINI_BACKOFF_BASE_SECONDS", 15.0)
    cap = _env_float("MICROGEN_GEMINI_BACKOFF_MAX_SECONDS", 180.0)
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= retries or not is_transient_gemini_error(exc):
                raise
            delay = min(cap, base * (2 ** attempt))
            delay += random.uniform(0.0, min(5.0, max(1.0, delay * 0.15)))
            print(f"[Gemini retry] {label} transient failure ({type(exc).__name__}: {exc}); "
                  f"retry {attempt + 1}/{retries} in {delay:.1f}s", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"{label} exhausted retries")

class GeminiLane:
    def __init__(self, stage: str, model: str = "") -> None:
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
        self.cooldown = _env_float("MICROGEN_GEMINI_LANE_COOLDOWN_SECONDS", 10.0)

    @property
    def queue_dir(self) -> Path:
        assert self.root is not None
        return self.root / "queue"

    @property
    def history_dir(self) -> Path:
        assert self.root is not None
        return self.root / "history"

    def _ticket_payload(self) -> dict[str, object]:
        return {"token": self.token, "host": self.host, "pid": self.pid, "stage": self.stage,
                "model": self.model, "created_utc": datetime.now(timezone.utc).isoformat()}

    def _write_ticket(self) -> None:
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
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
            return
        self._write_ticket()
        assert self.ticket is not None
        print(f"[Gemini lane] queued stage={self.stage} host={self.host} "
              f"ticket={self.ticket.name}; settling {self.settle:.0f}s", flush=True)
        time.sleep(self.settle)
        last_report = 0.0
        while True:
            self._remove_stale()
            tickets = self._tickets()
            names = [p.name for p in tickets]
            if self.ticket.name not in names:
                raise RuntimeError(f"Gemini lane ticket disappeared before acquisition: {self.ticket}")
            if tickets and tickets[0].name == self.ticket.name:
                time.sleep(self.claim_grace)
                self._remove_stale()
                tickets2 = self._tickets()
                if tickets2 and tickets2[0].name == self.ticket.name:
                    break
            now = time.time()
            if now - last_report >= 30.0:
                head = tickets[0].name if tickets else "<none>"
                print(f"[Gemini lane] waiting stage={self.stage} host={self.host}; "
                      f"queue={len(tickets)} head={head}", flush=True)
                last_report = now
            time.sleep(self.poll)
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop,
            name=f"gemini-lane-heartbeat-{self.pid}", daemon=True)
        self._heartbeat_thread.start()
        print(f"[Gemini lane] ACQUIRED stage={self.stage} host={self.host} model={self.model}", flush=True)

    def release(self, exc: BaseException | None = None) -> None:
        if not self.enabled:
            return
        if self.cooldown > 0:
            print(f"[Gemini lane] cooldown {self.cooldown:.0f}s before release "
                  f"stage={self.stage} host={self.host}", flush=True)
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
def gemini_lane(stage: str, model: str = "") -> Iterator[None]:
    lane = GeminiLane(stage=stage, model=model)
    if not lane.enabled:
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
