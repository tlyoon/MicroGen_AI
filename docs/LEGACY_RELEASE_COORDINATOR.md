# Fixed-owner, resumable legacy visual release coordinator

MicroGen_AI, 18 October 2026. Not MicroGen_AI_Web.

Five technical production releases were previously verified: 1.4, 1.5,
2.2, 2.6 and 3.1. This new module makes the release procedure reproducible
while preserving the existing fail-closed gates and two original backups.

## Contract

microgen_legacy_release_coordinator.py performs **one explicit phase**
per invocation, with the same immutable release-plan SHA256 on every PC.
It does not operate as a background daemon. It never automatically
publishes to Moodle or automatically releases another subchapter.

- The source root, candidate and coordinator evidence roots must not overlap.
- The plan refers to an existing Drive-native owner assignment separately
  pinned to an agreed SHA256. No reassignment without a new campaign.
- Exactly TWO named independent PC reviewers, different from the owner.
- All PCs use one SHA-pinned clean local Git commit.
- Each PC and release uses a local exclusive process lock. Stale locks require
  operator inspection; no automatic lock reclamation.
- One write-once stage receipt per designated host and phase in private
  Drive review storage; never overwrite a differing receipt.
- The candidate must pass the existing complete visual/audio release gate.
- TWO full, SHA256-verified backups are mandatory before promotion; review
  receipts must agree with the immutable source inventory and candidate.
- Production replacement needs a separate explicit single-subchapter token,
  while all other stages are read-only or restricted to protected backup paths.
- Both independent destination audits must pass BEFORE final technical status.
- Temporary Drive invisibility may be handled with a bounded wait of 0-300s;
  an existing file with the wrong checksum is rejected immediately.
- No fake WAVs, fabricated academic signatures, Moodle modifications, or
  external Google Cloud Storage distributed locks.

## Required plan fields

A single immutable JSON document with precisely these keys:

    schema_version: 1
    campaign_id: e.g. thomas-1-3-controlled-release-20261018
    section: e.g. 1.3
    source_root: absolute Drive course root
    candidate_dir: absolute private Drive accepted-candidate directory
    candidate_pdf_sha256: full 64-character verified corrected PDF digest
    assignment_path: Drive-native frozen owner-manifest JSON path
    assignment_sha256: full 64-character agreed assignment digest
    code_commit: same full Git commit on Dell-115, HP and Yoga6
    package_tag: safe unique local release package name
    secondary_package: protected private Drive backup destination path
    reviewers: exactly two uppercase Windows hostnames, e.g. HP and DELL-115
    evidence_dir: private Drive directory for immutable phase receipts

The plan itself is pinned by exact SHA256 bytes; distribute one immutable
copy and one agreed SHA to all machines. Status is never inferred from a
Git branch name or an unverified Google Drive file title.

## Explicit stage commands

Every command is shaped like:

    python microgen_legacy_release_coordinator.py
       --plan RELEASE_PLAN.json
       --plan-sha256 FULL_AGREED_PLAN_SHA256
       --phase PHASE

Execute the phases one by one, in this order:

1. Owner: preflight — verify candidate/sidecar/scene/AAC/PDF gate and owner.
2. Owner: prepare — create private local full original snapshot and stage
   accepted corrected PDF, MP4, embedded evidence and distinct legacy v2 receipt.
   On resume, validate a previous complete package instead of overwriting.
3. Owner: backup — create a complete independently recoverable protected
   Drive backup; if present, verify all hashes, never overwrite partial data.
4. TWO reviewer PCs: audit-backup — independently check protected backup
   and current original course bytes; store immutable reviewer receipts.
5. Owner: promote — ONLY with separate explicit arguments:
       --authorization AUTHORIZE_SINGLE_LEGACY_BUNDLE_REPLACEMENT
   Review receipts must agree with source/receipt hashes. Production
   replacement is guarded by the existing backup/rollback implementation.
6. TWO reviewer PCs: audit-destination — validate corrected media, receipt,
   original AAC and preservation of every unrelated source/Moodle file.
   Optional argument: --replication-wait-seconds 120.
7. Owner: complete — independently revalidate release destination and
   require TWO matching reviewer records. The resulting technical status
   explicitly does not authorize Moodle publication.

At any point, phase status shows current individual host checkpoints and
does not write to course folders.

## Crash recovery and boundaries

If the promotion operation succeeded but the coordinator itself crashed
before saving its immutable stage receipt, the owner can use phase
recover-promote. This inspects the saved underlying transaction result
and independently re-audits the current production folder BEFORE recreating
the missing phase receipt. It does NOT rerun production replacement.

Any failure before successful promotion must be investigated using the
two protected original backups; no automatic retry, cleanup, reallocation,
cloud mutex or silent removal of existing receipts is allowed.

Excluded from automatic technical releases until corrected: 1.1 stale WAVs,
1.2 incomplete historic candidate postrender proof, 3.2 video/slide mismatch,
5.6/7.2 truncated narration, and overflow 3.3, 3.10, 4.2, 4.6, 4.8.

Google Drive file sync is not atomic. Stage evidence is operational audit
metadata, not a cryptographic remote review signature. Independent reviewers
should be confirmed as the genuine designated machines before promotion.

Only HP, Dell-115 and Yoga6 participate. Zenbook excluded.
