# Gemini key-health cooldown within a MicroGen worker

## Why

During the isolated simultaneous HP/Yoga6/Dell-115 campaign on
15 October 2026, Gemini key #1 failed repeatedly on every page and
narration batch while key #2 served the requests. Each failure
triggered the standard fallback again, wasting network calls and time.

## How it works

- A worker that has at least two configured keys remembers a key's
  **non-billing authentication, authorization or quota-related failure**
  for a short process-local cooldown (default **120 seconds**).
- During that cooldown, subsequent calls in the **same Python process**
  prefer the remaining healthy keys without trying the unavailable key.
- Normal 503/transient high-demand responses use the existing bounded
  retry/backoff and do **not** mark a key unhealthy.
- Gemini billing/prepayment errors still follow the existing shared
  billing circuit, without being hidden by the cooldown.
- If every key is temporarily cooling down, the next request probes
  the configured pool again instead of failing only because of cache.
- After expiration, normal configured key priority resumes.

The cache uses SHA-256 key fingerprints in memory; actual API key contents
are never printed, stored in a new file, or copied between PCs. It is
not a distributed key-health database. Each new extraction/narration
subprocess begins with a clean in-memory health state.

## Controls

`MICROGEN_GEMINI_KEY_COOLDOWN_SECONDS=120` (default).

- Set to `0` to disable.
- Maximum effective cooldown is 3600 seconds, even if a higher value
  is supplied.
- Existing `MICROGEN_GEMINI_MAX_RETRIES`,
  `MICROGEN_GEMINI_TRANSIENT_RETRIES_PER_KEY`, request timeouts and
  billing safety controls are unchanged.

## Tests

The new offline suite verifies:
1. A known invalid key is not retried on the next request.
2. Expiration restores key priority.
3. The setting can disable cooldown.
4. Transient 503 failures still exercise existing retry logic.
5. Billing circuit behavior is retained.
6. All keys cooling off triggers a safe re-probe.
7. Single-key configurations are always attempted.

This reduces redundant requests **within a worker**. It does not
guarantee the first configured key will work or eliminate the need for
valid credentials, paid model availability and configured API quotas.
