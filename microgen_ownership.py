"""GCS generation-conditional cross-PC subchapter leases.

Google Drive synchronization is not a distributed lock. For multi-PC work,
require a GCS bucket with generation preconditions (strong compare-and-swap).
The lock covers one campaign/subchapter, not merely Gemini API requests.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any


class LeaseBusy(RuntimeError):pass
class LeaseLost(RuntimeError):pass


def _is_precondition_failed(exc: Exception) -> bool:
    return getattr(exc, "code", None) == 412 or type(exc).__name__ == "PreconditionFailed"


def lease_object_key(campaign: str, subchapter: str) -> str:
    if not campaign or len(campaign) > 120 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", campaign):
        raise ValueError("Campaign ID must be 1–120 safe characters")
    if not re.fullmatch(r"\d+\.\d+", subchapter):
        raise ValueError("Invalid subchapter ID")
    digest = hashlib.sha256(campaign.encode("utf-8")).hexdigest()[:20]
    return f"microgen/v1/{digest}/{subchapter}.json"


class GCSLease:
    def __init__(
        self, bucket, campaign: str, subchapter: str, *,
        ttl_seconds: float = 180, renew_seconds: float = 45,
        clock=time.time, token: str | None = None,
        host: str | None = None,
        run_heartbeat: bool = True,
    ):
        if ttl_seconds < 90 or renew_seconds < 5 or renew_seconds >= ttl_seconds / 2:
            raise ValueError("Lease TTL must be >=90s and renewal < half TTL")
        self._bucket = bucket
        self.key = lease_object_key(campaign, subchapter)
        self._clock = clock
        self.ttl = ttl_seconds
        self.renew = renew_seconds
        self.token = token or uuid.uuid4().hex
        self.host = host or socket.gethostname()
        self._heartbeat_enabled = run_heartbeat
        self._blob = None
        self._generation = None
        self._lost: Exception | None = None
        self._stop = threading.Event()
        self._thread = None
        self._guard = threading.Lock()

    def _payload(self) -> str:
        now = self._clock()
        return json.dumps({
            "schema_version": 1, "token": self.token,
            "host": self.host, "expires_epoch": now + self.ttl,
            "renewed_utc": datetime.now(timezone.utc).isoformat(),
        }, separators=(",", ":"))

    def _get(self):
        blob = self._bucket.blob(self.key)
        blob.reload()
        state = json.loads(blob.download_as_bytes().decode("utf-8"))
        return blob, state

    def acquire(self) -> "GCSLease":
        blob = self._bucket.blob(self.key)
        try:
            blob.upload_from_string(
                self._payload(), content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if not _is_precondition_failed(exc):
                raise
            try:
                blob, record = self._get()
            except Exception as read_error:
                raise LeaseBusy(f"Lease occupied/unreadable: {self.key}") from read_error
            # Invalid records fail closed, not forcibly stolen.
            expiry = record.get("expires_epoch")
            if not isinstance(expiry, (int, float)):
                raise LeaseBusy("Malformed lease; manual recovery required")
            if expiry + 20 >= self._clock():
                raise LeaseBusy(f"Owned by {record.get('host', 'unknown')}; expires at {expiry}")
            try:
                blob.upload_from_string(
                    self._payload(), content_type="application/json",
                    if_generation_match=blob.generation,
                )
            except Exception as takeover_error:
                if _is_precondition_failed(takeover_error):
                    raise LeaseBusy("Another worker acquired the expired lease") from takeover_error
                raise
        self._blob = blob
        self._generation = blob.generation
        self.assert_held()
        if self._heartbeat_enabled:
            self._thread = threading.Thread(target=self._heartbeat, daemon=True,
                                            name="MicroGenGCSLeaseHeartbeat")
            self._thread.start()
        return self

    def _refresh(self):
        blob, record = self._get()
        if record.get("token") != self.token:
            raise LeaseLost("Lease ownership token has changed")
        if record.get("expires_epoch", 0) < self._clock():
            raise LeaseLost("Lease expired before renewal")
        try:
            blob.upload_from_string(self._payload(), content_type="application/json",
                                    if_generation_match=blob.generation)
        except Exception as exc:
            if _is_precondition_failed(exc):
                raise LeaseLost("Lease superseded during renewal") from exc
            raise
        self._blob = blob
        self._generation = blob.generation

    def _heartbeat(self):
        while not self._stop.wait(self.renew):
            try:
                with self._guard:
                    self._refresh()
            except Exception as exc:
                self._lost = exc
                self._stop.set()
                return

    def assert_held(self):
        if self._blob is None or self._lost is not None:
            raise LeaseLost("No active lease or heartbeat failure") from self._lost
        with self._guard:
            blob, state = self._get()
            if state.get("token") != self.token or state.get("expires_epoch", 0) <= self._clock():
                raise LeaseLost("Lease lost or expired")
            self._generation = blob.generation

    def release(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.renew + 1)
        with self._guard:
            if self._blob is None:
                return
            try:
                blob, state = self._get()
                if state.get("token") == self.token:
                    blob.delete(if_generation_match=blob.generation)
            except Exception as exc:
                # A lost/deleted lease must not delete the successor's lock.
                if not (_is_precondition_failed(exc) or
                        type(exc).__name__ in ("NotFound", "LeaseLost")):
                    raise
            finally:
                self._blob = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, _type, _value, _trace):
        self.release()


def from_gcs_bucket(name: str, campaign: str, subchapter: str) -> GCSLease:
    """Only imports GCS when the user explicitly enabled multi-PC leases."""
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "Multi-PC leasing requires 'pip install google-cloud-storage' "
            "and an IAM-authorized GCS bucket."
        ) from exc
    if not name:
        raise ValueError("A cloud bucket is required for distributed leasing")
    return GCSLease(storage.Client().bucket(name), campaign, subchapter)
