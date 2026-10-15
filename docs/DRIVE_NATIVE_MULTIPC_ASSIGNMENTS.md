# Multi-PC campaigns without external Google Cloud locking

## Architecture and safety contract

MicroGen_AI uses the existing `gemini_lane.py` FIFO/circuit breaker to reduce
overlapping Gemini requests on a shared Google Drive synchronization folder.
This FIFO **is advisory**: Drive's eventual synchronization does not provide an
atomic distributed mutex.

**Publication ownership** is governed by a separate, explicit, immutable
campaign assignment file (`microgen_drive_assignments.py`). Assign each source
subchapter to exactly ONE registered Windows host. All workers must specify
the identical SHA-256 of the exact manifest bytes, the same campaign identifier,
and the same shared source root. Only the named host may execute or publish.
The runtime rereads the pinned assignment before every stage, while subprocesses
run, and immediately before source-adjacent publication. Loss of the manifest,
changed hash, unregistered machine, or mismatched source tree **stops the job**.

This is a deterministic, preassigned **single-writer campaign**, not a dynamic
file-based lease or a guarantee of mutual exclusion against workers using a
*different* manifest, campaign ID, or bypassing MicroGen. All computers must
agree on one digest **before starting**. Do not automatically take over a dead
host's work; automatic failover is disabled. This avoids creating a false
distributed-lock guarantee on top of Drive synchronization.

## Manifest (one file shared on Google Drive)

Example (adjust source and hosts before use):

```json
{
  "schema_version": 1,
  "campaign_id": "thomas-fall-2026",
  "source_root": "G:\\My Drive\\Projects\\Thomas_calculus_13ed",
  "participants": ["HP", "DELL-115", "YOGA6"],
  "owners": {
    "8.4": "HP",
    "8.5": "DELL-115",
    "8.6": "YOGA6"
  }
}
```

The source root must be identical on all machines. Use real hostnames from
`[Environment]::MachineName` and only explicitly listed targets.
Keep a reviewed version of the manifest with campaign documentation.
Only one coordinator may issue a manifest for a campaign. Freeze the file
once the SHA-256 has been distributed. Do not edit it while workers run.

## One-time participating PC configuration

Keep the Git repo and heavy scratch *local* on each PC; source and final output
remain in the authorized writable Drive tree.

Set the same Drive-based Gemini queue directory for the relevant Windows user.
The queue is intentionally separate from a Git working tree:

```powershell
$lane = 'G:\My Drive\MicroGen_Coordination\gemini_lane'
if (-not (Test-Path $lane)) { throw 'Coordinator must create shared lane first' }
[Environment]::SetEnvironmentVariable('MICROGEN_GEMINI_LANE_DIR', $lane, 'User')
$env:MICROGEN_GEMINI_LANE_DIR = $lane
```

Confirm each worker can see the *same* queue contents after synchronization.
The queue has heartbeat/stale-ticket handling but cannot guarantee serialization
if multiple Google Drive replicas are temporarily divergent.

## Safe, free, assignment-only two-PC test

```powershell
$manifest = 'G:\My Drive\MicroGen_Coordination\campaigns\thomas-fall-2026.json'
$sha = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLower()
$base = "$env:LOCALAPPDATA\MicroGen_Scratch"
python microgen_batch.py --multi-pc --check-assignments `
  --campaign-id thomas-fall-2026 --assignments-file $manifest `
  --assignments-sha256 $sha `
  --source-root 'G:\My Drive\Projects\Thomas_calculus_13ed' `
  --work-root $base --targets 8.4
```

Run on HP (must accept) and Dell (must reject). Reverse with assigned `8.5`:
Dell must accept and HP must reject. Deliberately modify an **isolated test**
manifest after its checksum is recorded: both must reject the changed digest.
This mode does **not** import Docling, call Gemini, allocate cloud resources,
or produce lecture media.

Never compute the digest independently against different, locally edited
manifests. Share the **same agreed digest** via the coordinator before
starting work. A digest generated from each PC's conflicting file could
defeat the intended agreement.

## Production invocation

Only after both hosts passed the assignment-only test, and after confirming
that the shared Gemini queue is visible:

```powershell
python microgen_batch.py --repo "$env:LOCALAPPDATA\MicroGen_AI" `
  --source-root 'G:\My Drive\Projects\Thomas_calculus_13ed' `
  --work-root "$env:LOCALAPPDATA\MicroGen_Scratch" --targets 8.4 `
  --multi-pc --campaign-id thomas-fall-2026 `
  --assignments-file $manifest --assignments-sha256 $sha --fail-fast
```

Provide **only the targets assigned to the current hostname**. A wrong target
fails before any Gemini/TTS request. Existing successful verified outputs
are retained and skipped.

## Recovery

If HP disconnects while holding `8.4`, its assignment remains HP. Do **not**
automatically hand it to Dell. First confirm HP worker has stopped, capture
checkpoints, freeze all campaign processes, then prepare a **new version**
of the manifest and new hash and distribute it to all workers. Only resume
after every worker acknowledges the same new hash. Old workers fail their
pinned hash checks when they see the replacement.

## Scope and limitations

- No Firestore/GCS/Cloud Storage project, bucket, SDK or credential is required.
- Existing `microgen_ownership.py` and `microgen_lease_doctor.py` may remain
  for legacy test compatibility but are **not invoked** by the new
  `--multi-pc` code path. Passing their historical unit tests does not
  indicate the campaign uses GCS.
- Windows Job Object stage fencing remains active through the existing
  `lease.assert_held()` adapter on preassigned workers.
- Stale/out-of-sync Drive replicas can remain available locally, so an
  external administrative freeze is required when changing assignments.
- The Gemini FIFO provides best-effort API load coordination, not job ownership.
- No automatic publication to students or scientific approval is implied.
