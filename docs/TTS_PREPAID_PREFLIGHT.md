# PR #47 — Prepaid technical preflight

Before independent paid acoustic recognition, the unattended campaign invokes the complete read-only release audit **without** an acoustic receipt. It requires all other mandatory technical checks to pass: source math/lexicon, pinned WAV/voice manifest, PCM integrity, actual MP4 checks, and strict video length under 600 seconds. The only temporary blocker permitted at this phase is the acoustic result that the campaign is about to acquire. No human approvals are required, and no provider is called or QA folder created on a preflight failure.

This prevents wasted API calls on source assets that can never be technically cleared in the current run. The test suite verifies failed provenance, altered audio, over-600-second video, and the happy path, with recognition callbacks never executed on invalid assets. Use only a separate staged lecture, not historical production files.
