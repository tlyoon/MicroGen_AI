# MicroGen_AI continuity checkpoint

**Workstream:** Original `tlyoon/MicroGen_AI` — Thomas Calculus source-grounded lecture/video generation and conservative TTS QA. **Not** `MicroGen_AI_Web`.

**History recovered:** The predecessor continuation series is `1. Generate Thomas calculus` through `7. Generate thomas`. Historical account/project summaries were accessible, but the complete transcript of the immediate predecessor was not independently retrieved. Verify all claims against repository and HP evidence before action.

## Authoritative contract (30 October 2026)

- **Only the HP computer** is authorized for local execution. Do not execute, sync, change, or inspect Dell-115 or Yoga6 for this original workstream.
- Preserve protected Google Drive source materials, original narration, historical WAV/MP4, manifests, and figure mapping; diagnostic records belong in isolated HP AppData or other approved non-source folders.
- Google Cloud TTS is allowed **only for bounded, isolated troubleshooting** (historically at most 500 normalized characters and one actual API attempt per diagnostic). It is **not the default formal production TTS provider**. No new paid batch or auto-publication.
- Offline ASR is evidence for review, not verified phonetic identity. A sound-alike recognition variant must not block acceptable WAV; clear confirmed math-letter defects (e.g. mathematical c. said as "circa") remain important.
- No automatic approval, publication, or production WAV rewriting based solely on recognizer output. Validate original PDF, images, mathematics, equation cues, audio provenance and voice before release.

## Latest independently verified repository checkpoint

- Repository: https://github.com/tlyoon/MicroGen_AI , branch `main`.
- PR #217 merged at `05f817fd3b7d2bd25f470a5a032eb0ed68fdfcd8`: generalized, conservative math pronunciation normalization and source/WAV/ASR-bound diagnostics.
- PR #218 merged at `388c33ffc11aa18cbf536c3154ddf622f99c0b68`: automatic immutable post-TTS pronunciation evidence capture and ASR candidate catalog. Historical HP full regression: 1085 passed, 5 skipped, 159 subtests; hosted CI four jobs passed.
- Real historical Thomas §2.5 evidence: 23 original WAVs + 23 SHA-bound offline ASR receipts; 69 source pronunciation risks, 91 distinct *unverified* transcript differences, 11 possible technical-term difference cases, not 91 proven defects.
- Separate Serway §1.1 is an eight-page offline source-grounded draft, **not** a complete formal voice-matched video. Formal provider remains unconfigured.

## Continuation work started 30 October 2026

- Checked HP connection and existing isolated git checkout at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261030_HP_PR218_PRONUNCIATION_EVIDENCE_PIPELINE`.
- Created `feature/hp-pr219-preserve-asr-insertions-omissions-20261030` from verified `origin/main` commit `388c33ff`.
- Found a concrete PR #218 defect: purely inserted/deleted ASR word groups were discarded by the candidate aggregator despite a defined advisory alignment category.
- Added a regression test first: red (2 passed, 1 failed) on unchanged code, then minimal production fix: green (8 passed) in the focused evidence-pipeline tests.
- Confirmed actual saved Thomas §2.5 QA data contains 200 raw word mismatch groups, including 9 insertion/deletion groups, which require preservation; original data remains unchanged.
- **HP validation:** regression-first focused test failed as expected before fix, then 8/8 focused tests passed. Broader `python -m pytest tests -q` completed `1081 passed, 10 skipped, 159 subtests passed, 2 warnings, exit 0` (168.54s). Root-level `python -m pytest -q` and hosted PR CI must be checked independently. These tests do not certify production media, voice or publication.

## Priority after PR #219

1. Finish HP full regression, commit and push the exact tested branch, open PR #219, verify all hosted CI jobs and merge only if green.
2. Re-run read-only original Thomas §2.5 evidence capture using saved SHA-bound ASR/WAV data, outputting a new immutable HP-external receipt; do not modify original evidence or production WAVs.
3. Triage recurring genuine technical-word candidates by listening/independent acoustic checks. Treat homophones/ASR noise as advisory and never invent repairs.
4. Continue independent source-to-video QA on a fresh lecture once formal production TTS voice/provider and permission requirements are satisfied. Existing Serway §1.1 draft is not publishable.
5. Keep this checkpoint current with exact commit, tests, blockers and next action after each implementation segment.
