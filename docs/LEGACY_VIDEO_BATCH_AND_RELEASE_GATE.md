# Fixed-owner legacy video batch and release gate

MicroGen_AI, 17 October 2026 (distinct from MicroGen_AI_Web).

## Safety

The existing Drive-native immutable assignment manifest (schema v1)
owns all jobs. Each target has exactly one named Windows PC, pinned to one
coordinator-agreed SHA-256. The 51-section corrected-PDF manifest is pinned
separately, and each PDF is checked against its own SHA-256.

The program microgen_legacy_video_batch.py provides:
- Clean local Git checkout pinned to the identical full 40-character SHA.
- Read-only preflight by default. Explicit --execute for local candidates.
- Local exclusive O_EXCL lock; single per-host FIFO worker.
- Local checkpoint and per-section logs, without any remote lock service.
- Resume only after verifying original and candidate source/MP4/AAC hashes.
- Repeated assignment and candidate checksum checks during rendering.
  On mismatch, attempt to terminate the child process tree and stop.
- No automatic failover, source overwrite, Moodle publication or forged
  source-bound completion receipt.

Google Drive is NOT an atomic mutex. The coordinator must freeze and
distribute the same approved manifest digest to every PC in advance.
Never automatically reassign work during Drive synchronization delay.

## Coordinator assignment manifest

Place one immutable file named campaign.json in the agreed Drive campaign
directory. Its schema matches microgen_drive_assignments.py:

    {
      "schema_version": 1,
      "campaign_id": "thomas-video-visual-pilot-20261017",
      "source_root": "G:\\My Drive\\ZCA110_2627_SEM1\\MCQ_generation\\Thomas_calculus_13ed",
      "participants": ["DELL-115", "HP", "YOGA6"],
      "owners": {
        "2.2": "DELL-115",
        "2.6": "HP",
        "3.1": "YOGA6"
      }
    }

PDF candidate manifest:
G:\My Drive\MicroGen_Experimental_Review_20261016\Legacy_Repair_Candidates_20261016\footer_only_51_consolidated_20261016.json

The coordinator records (1) exact manifest SHA-256, (2) exact candidate
manifest SHA-256, (3) full Git commit, and (4) campaign ID. All workers
must check identical values, not generate independent replacement digests
from possibly stale Drive replicas.

## Runbook on the designated host

Use the clean local repository and pre-approved worker targets only.
Example PowerShell assignments:

    $code = Join-Path $env:LOCALAPPDATA 'MicroGen_AI_Verified_20261016'
    $base = Join-Path $env:LOCALAPPDATA 'MicroGen_RepairPilot_20261016'
    $src = 'G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed'
    $assign = 'G:\My Drive\MicroGen_Experimental_Review_20261016\Video_Batch_Coordination\campaign.json'
    $pdfManifest = 'G:\My Drive\MicroGen_Experimental_Review_20261016\Legacy_Repair_Candidates_20261016\footer_only_51_consolidated_20261016.json'
    $assignmentSha = '<agreed-64-character-manifest-sha256>'
    $candidateSha = '<agreed-64-character-pdf-manifest-sha256>'
    $commit = '<full-agreed-40-character-Git-commit>'

Use microgen_legacy_video_batch.py with arguments:

    --manifest <assignment-path>
    --manifest-sha256 <agreed-64-sha>
    --candidate-manifest <PDF-manifest-path>
    --candidate-sha256 <agreed-64-sha>
    --campaign-id thomas-video-visual-pilot-20261017
    --source-root <source-root>
    --pdf-root <LOCALAPPDATA/../BatchFooter_20261016>
    --output-root <LOCALAPPDATA/../VideoCandidatesBatch_20261017>
    --targets 2.2
    --code-commit <full-Git-commit>

Without --execute the command only verifies inputs and reports a plan.
With --execute it writes local MP4 candidates and checkpoints but does
NOT write into the course source tree or publish to Moodle.

On interruption, inspect checkpoint/logs and ensure the previous process
is dead before manually clearing a stale local lock. Never auto-reassign.

## Separate release-readiness gate

Run microgen_legacy_release_gate.py with:
--source, --corrected-pdf, --video-dir, --section, and
--expected-pdf-sha256 for the individual section.

It independently checks the strict PDF gate, source/media hashes,
AAC compressed-stream identity, scene/pixel/timing reports and narration
provenance. It ALWAYS returns may_publish=false and creates no receipt.

Missing slide-aligned sidecars and stale WAV lists are release blockers;
absent WAVs with exact preserved AAC can be an advisory. Known truncated
narration titles (5.6 and 7.2) remain blocked.

Known exclusions:
- 1.1: 17 slides but 22 stale WAVs.
- 5.6 and 7.2: incomplete opening narration title.
- 3.3, 3.10, 4.2, 4.6, 4.8: unresolved overflow/token reflow.
- Any dirty code checkout, changed manifest, owner mismatch or hash drift.

The user directed MicroGen_AI to assume academic review is complete,
but no signed reviewer record is fabricated. Production replacement
still requires full backups, genuine completion receipts and cross-PC
destination hash verification in a separate step.
