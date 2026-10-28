# PR #44 — Verify v2 acoustic source snapshots during release audit

New v2 independent audio-screen receipts include SHA-256 of *all* WAVs, the voice-manifest, and the narration sidecar. A later release audit rehashes those exact files and refuses a stale, incomplete, extra-field or tampered snapshot. This complements the PR #43 in-flight snapshot guard and prevents a receipt from being reused after the original narration changes.

Historical v1 receipts remain parseable (with their preexisting WAV/voice/spoken-text checks), but do not acquire v2 snapshot claims. The verifier never invents model transcripts, human approvals, or publication. Failure requires generating fresh genuine evidence, not bypassing a technical gate.
