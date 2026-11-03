# Incremental private PDF campaign planning

Use `microgen_private_incremental_campaign.py` with the same case manifest
used by `microgen_private_unified_campaign.py` and a previously validated
private unified receipt directory.

The planner reads existing receipts, verifies both subordinate receipt
hashes, then checks source PDF bytes; canonical private packet/draft JSON;
and authored stage contract/narration bytes. Only IDs, decision labels and
changed field names are printed. It does not read out or publish source text,
regenerate slides or videos, call a model, or alter a PDF.

Decisions:
- `TRACKED_INPUTS_UNCHANGED_PRESERVE_RECEIPT`: preserve existing evidence;
  this is **not** a new complete audit of plan, figures, rendered outputs,
  current source code or academic semantics.
- `CHANGED_INPUT_REVALIDATE_SECTION`: run existing unified gates against
  the *current* case manifest for that section only; do not rerun unrelated
  sections or regenerate media.
- `MISSING_INPUT_RESTORE_BEFORE_REVALIDATION`: recover a missing input.
- `NEW_SECTION_REQUIRES_FULL_GATES`: create source-bound authoring evidence
  and run standard gates once, without per-PDF source-code patches.

The earlier receipt must be an intact locally retained artifact; its
SHA256 identity is not a cryptographic signature or independent proof of
trust. In particular, source-only matching cannot authorize publication.
