# PR #36 — External reviewer attestation trust boundary

Previously, the TTS read-only release checker accepted bare JSON `{"approved": true, "reviewer": "..."}` for academic, figure, element-highlighting and per-slide listening approvals. Such text can be fabricated by a generator and must never count as independent human review.

This PR requires role-separated **HMAC-SHA256 authenticated reviewer receipts**. Independent review tooling, not TTS synthesis or an assistant, retains strong (32+ byte) signing keys outside the lesson folder and source control. A named reviewer, reviewer role, key ID, UTC or offset-aware review time, SHA-256 binding and signed review content are mandatory; any edits break signature validation. The four roles are `listening`, `academic`, `figures` and `highlights`. The approval auditor fails closed if external trusted keys are not explicitly passed; its CLI optionally accepts `--review-trust-root` pointing to a role-key JSON mapping **outside the lecture folder**. Do not place reviewer secrets in repo, lesson staging, or generated QA reports.

Cryptographic validity proves access to a signing key, not that a person genuinely listened to the video. Reviewer key ownership, rotation, audit trail, identities and consent remain the responsibility of an independent publishing/review system. This feature only strengthens the evidence boundary; it neither signs reviews automatically nor promotes media.

No new third-party dependency. Regression tests include tampering, forged plain approvals, role confusion, reviewer changes, stale audio SHA, absent trust roots and valid external attestations.
