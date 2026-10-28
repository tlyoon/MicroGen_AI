# PR #43 — Acoustic input snapshot consistency

At the start of independent acoustic recognition, the QA engine SHA-256 pins each WAV, the voice-provenance manifest, and narration sidecar (if present). After the last recognition call it rehashes the same files. If any bytes have changed, the entire recognition receipt is rejected before serialization, even when both model transcripts are textually correct. This defends against concurrent jobs and stale evidence. A hash mismatch is a technical blocker, never a request for manual approval.

The test-only recognizer deliberately alters scratch WAV, provenance manifest, and sidecar to confirm each mutation prevents a misleading success receipt. No production files or original teaching assets are changed.
