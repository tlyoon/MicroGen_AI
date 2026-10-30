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
- PR #219 merged at `1bccd453777413ad6329f2b50dc7d7cb2d78b730`: preserve purely inserted/omitted recognized-word hypotheses. Tested HP root-level 1081 passed, 10 skipped, 159 subtests, hosted CI 4/4 successful. Historical branch PR #219 reported in section below is complete.
- Real historical Thomas §2.5 evidence: 23 original WAVs + 23 SHA-bound offline ASR receipts; 69 source pronunciation risks, 91 distinct *unverified* transcript differences, 11 possible technical-term difference cases, not 91 proven defects.
- Separate Serway §1.1 is an eight-page offline source-grounded draft, **not** a complete formal voice-matched video. Formal provider remains unconfigured.

## Continuation work started 30 October 2026

- Checked HP connection and existing isolated git checkout at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261030_HP_PR218_PRONUNCIATION_EVIDENCE_PIPELINE`.
- Created `feature/hp-pr219-preserve-asr-insertions-omissions-20261030` from verified `origin/main` commit `388c33ff`.
- Found a concrete PR #218 defect: purely inserted/deleted ASR word groups were discarded by the candidate aggregator despite a defined advisory alignment category.
- Added a regression test first: red (2 passed, 1 failed) on unchanged code, then minimal production fix: green (8 passed) in the focused evidence-pipeline tests.
- Confirmed actual saved Thomas §2.5 QA data contains 200 raw word mismatch groups, including 9 insertion/deletion groups, which require preservation; original data remains unchanged.
- **HP validation:** regression-first focused test failed as expected before fix, then 8/8 focused tests passed. Broader `python -m pytest tests -q` completed `1081 passed, 10 skipped, 159 subtests passed, 2 warnings, exit 0` (168.54s). Root-level `python -m pytest -q` and hosted PR CI must be checked independently. These tests do not certify production media, voice or publication.

## Current continuation: HP PR #220 numeric-ASR token alignment (30 October 2026)

- Branch `feature/hp-pr220-numeric-asr-token-alignment-20261030`, based on merged PR #219 `1bccd453777413ad6329f2b50dc7d7cb2d78b730`.
- Regression-first discovery: `_word()` removed every digit; numerical narration expected `7` became an empty token, whereas Vosk returned `seven`. This fabricated blank alignment spans and inaccurate word-pair hypotheses. Test confirmed defect (1 failed) before code change.
- Conservative correction: one-digit tokens `0` through `9` are mapped to their unambiguous English names; multi-digit tokens are retained as literal digits rather than guessing context-dependent speech. Recognizer uncertainty remains advisory, no new automatic repairs.
- Focused pronunciation tests: `24 passed, 6 subtests passed` after fix. **Full HP root-level `python -m pytest -q`: 1083 passed, 10 skipped, 159 subtests passed, 2 existing warnings, 0 failed, exit 0, 170.32 seconds.** Hosted PR CI must be checked independently on exact PR head.
- **Actual original Thomas §2.5 no-write reproducibility:** unchanged source and 23 original WAVs plus 23 SHA-verified independent Vosk evidence; new immutable receipt `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261030_HP_PR220_REAL_THOMAS_NUMERIC_ALIGNMENT\pronunciation_evidence_fcce1b42188775183c32.json`, **89** distinct unverified candidates, **11** technical-term hypotheses, **12** homophone/ASR alternatives and **11** insertion/omission pairs. Immediately previous, also immutable PR219-baseline result had 98 distinct candidates, 11 technical terms, 10 homophone alternatives and 21 alignment-only. **This is a noise-reduction comparison, not nine confirmed audio defects fixed.** No formal provider or acoustic release.
- Independent HP comparison of pre/post evidence: all 23 audio SHA-256 values, the original script SHA-256 and provider provenance manifest SHA-256 match exactly. The new 89-candidate catalog has 28 removed/changed pairs and 19 added/changed pairs relative to the previous 98; the totals are not a count of confirmed audio problems.
- Original Serway §1.1 remains an eight-page offline draft, not a source-to-video publishable lecture.

## Next priorities after PR #220

1. Complete full HP regression, push and verify PR #220 hosted CI, merge only if all required checks pass. Update checkpoint with exact final SHA.
2. Produce SHA-bound **timed** candidate evidence for the remaining 11 technical-word hypotheses from real WAV + offline ASR without claiming exact phonetic certainty, and prepare bounded source-preserving listening/independent cross-check clips only where timestamps are unambiguous.
3. Improve independently corroborated pronunciation defects conservatively; keep sound-alike homophones and uncertain ASR spellings advisory. No automatic production WAV overwrite.
4. Choose a compatible formal TTS voice/provider within the project contract and finish a complete Serway §1.1 source-to-video proof before release; do not silently select diagnostic Google Cloud TTS as formal provider.
5. Keep this checkpoint current after every merged PR and preserve HP-only execution.
