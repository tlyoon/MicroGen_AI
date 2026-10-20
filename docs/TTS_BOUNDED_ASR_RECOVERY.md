# PR #48: acoustic-service retry classification

Transient 408/429 rate-limit, 5xx outage and timeout conditions receive at most three recognition attempts with bounded 1 s and 3 s delays. Hard quota exhaustion, authentication errors, unsupported models and malformed responses fail immediately. An unknown error is not retried. Never claim verification on partial or missing transcripts. No credential values or raw provider errors appear in outward exception messages. No human approval is necessary for automated QA.
