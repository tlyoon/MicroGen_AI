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
- PR #219 merged at `1bccd453777413ad6329f2b50dc7d7cb2d78b730`: preserve purely inserted/omitted recognized-word hypotheses. Tested HP root-level 1081 passed, 10 skipped, 159 subtests, hosted CI 4/4 successful.
- PR #220 merged at `d569b7525e00153bfa48a3ca37f802692576e85a`: numerical tokens preserved in ASR alignment. HP root-level 1083 passed, 10 skipped, 159 subtests; GitHub run 41061698504 had 4/4 Windows/Ubuntu successful. Original 23 slide WAV/source/provider hashes unchanged.
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

## Current workstream — HP PR #221: real SHA-bound technical-term ASR time suggestions

- New branch `feature/hp-pr221-hash-bound-asr-timing-index-20261030`, based on verified merged PR #220 main SHA `d569b7525e00153bfa48a3ca37f802692576e85a`.
- New `microgen_tts_candidate_timing.py`: **offline only**, validates real source WAV hashes, independent per-slide Vosk report SHA and WAV identity, plausible ASR word times and confidences against actual PCM duration, and independently recomputes the exact source-bound pronunciation evidence before time-indexing technical-term hypotheses.
- Finds unique contiguous ASR word spans; repeated matches remain `AMBIGUOUS_ASR_SPAN` with no timing guess. Every candidate remains unconfirmed, unrepaired, and nonpublishable. No Cloud/Gemini/Whisper/TTS calls or WAV/MP4/source writes. Refuses existing/external-source output overwrites.
- Real original Thomas §2.5: all **11** technical-term hypotheses located at unique *ASR-recognized* slide intervals; 23 original WAVs and 23 SHA-bound offline Vosk reports; saved new separate immutable HP AppData file `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261030_HP_PR221_THOMAS25_TIMED_TECHNICAL_CANDIDATES.json`. These are approximate ASR timing suggestions, **not verified phoneme boundaries**. Examples: slide 14 cosine as `coast sign` near 45.36–45.96 s (ASR min confidence 0.7172); slide 11 theorem as `serum` near 0.03–0.39 s (ASR min confidence 0.49468).
- Focused regression: **28 passed and 6 subtests passed**, covering ambiguous duplicates, forged evidence, SHA drift, impossible ASR time and immutable output rejection. **HP full root-level `python -m pytest -q`: 1087 passed, 10 skipped, 159 subtests passed, 2 known warnings, exit 0, 165.27s.** GitHub four-job CI remains independently required before merge.

## Next priorities after PR #221

1. Finish HP root-level regression, commit/push PR #221, check all four hosted CI jobs, merge only if successful, and record final merge SHA.
2. Generate selectively bounded, SHA-bound short listening excerpts at verified *ASR-suggested* positions, in **external output-only** directories. Consider independent audio model/phoneme evidence where feasible; never infer phonetic correctness from Vosk alone.
3. Fix **only** sufficiently corroborated pronunciation problems and re-verify sound; keep homophones and uncertain ASR spellings advisory. Do not auto-overwrite original WAVs or block otherwise acceptable speech.
4. Resolve formal production TTS voice/provider within the contract, then run a source-to-video Serway §1.1 integration demonstration with independently verifiable source, figures, narrated mathematics and A/V QA, without automatic publication.
5. Continue HP-only execution; synchronize checkpoint with each merged PR.

## PR #222 — bounded technical-audio excerpt evidence (31 October 2026)

- Parent verified main: PR #221 merged at `3c527200e1a56e07c08831a0b76834d72a558c38`. PR #221 HP validation: 1087 passed, 10 skipped, 159 subtests; all four hosted CI jobs succeeded.
- Current branch: `feature/hp-pr222-sha-bound-technical-audio-excerpts-20261031`, based on the verified PR #221 main commit.
- New `microgen_tts_candidate_clip_bundle.py` re-verifies SHA-anchored offline timing/evidence against the source and all independent Vosk receipts, applies a bounded nonoverlapping time window to uniquely found ASR suggestions, extracts mono PCM16 with existing byte-accurate source-preserving `microgen_tts_audio_snippets.extract_clips`, saves review metadata, confirms original evidence and clip hashes, and atomically publishes to a fresh *external* output folder. Ambiguous ASR spans are skipped, never guessed. No TTS API, regenerated production voice, pronunciation approval or release.
- New `tests/test_microgen_tts_candidate_clip_bundle.py` covers exact source PCM byte identity, all hash/report provenance, immutable output/no overwrite, deliberately ambiguous duplicate span, budgets, source-folder/My Drive protection, tampered timing and WAV identity changes.
- HP focused 13 passed + 3 subtests. Actual 23 original Thomas §2.5 WAVs and SHA-bound independent ASR/evidence produced **11 external short clips across 8 slides, total 16.609 seconds**, all clip SHA verified and **all 23 source WAV SHA rechecked unchanged**, zero skipped, zero provider calls. The new immutable external bundle is `%LOCALAPPDATA%\\MicroGen_AI_Checkpoints\\20261031_HP_PR222_THOMAS25_TECHNICAL_AUDIO_CLIPS`; review index `review_index.json`. All clips are **unreviewed ASR-hypothesis candidate audio**, not independently established mispronunciations. `publication_allowed=false`.
- HP root-level full regression `python -m pytest -q` completed **1092 passed, 10 skipped, 162 subtests passed, 2 existing warnings, exit 0, 171.77 seconds**. Hosted CI and PR merge must be recorded independently; an opened PR does not count as merged.
- Reusable operation and safety guide: `docs/HP_PR222_CANDIDATE_AUDIO_EXCERPTS.md`.

### Next justified priorities after PR #222

1. Require exact tested commit, full HP tests and all four hosted CI jobs green prior to merger; record verified main merge SHA.
2. Conduct independent acoustic checks against these WAV excerpts (e.g., audio-signal integrity and comparison to spoken mathematical intent), but do not claim a word was mispronounced based solely on Vosk spelling. Only strong, reproducible evidence can justify isolated correction and fresh full QA; original production WAVs remain protected.
3. Move to a truly complete second-source Serway §1.1 lecture from the original source and mapped figures, narration and a separately approved formal voice/provider, then verify slide/audio/video/academic consistency. Google Cloud voice stays diagnostics-only unless owner changes policy.
4. Keep the persistent checkpoint accurate with exact PR/test evidence; only HP is permitted for local execution.

## PR #223 — independent physical-acoustic candidate triage (31 October 2026)

- Parent `main`: verified PR #222 merged at `ddde3baba5ae9fa62aed3520c7f82fd085ab8fde`; HP-only branch `feature/hp-pr223-independent-acoustic-triage-20261031`.
- New `microgen_tts_candidate_signal_screen.py` measures PCM RMS, zero signal and frame clipping **independently of ASR transcript spelling**. Each clip and the original slide WAV are SHA-256 revalidated before and after; rejection for stale/source-drift, forged phonetic approval, symlinks, path escape and duplicate clip IDs. Creates only fresh outside-source immutable JSON.
- Five focused tests pass. Real Thomas §2.5 original 11 external excerpts: independent physically measured **11 clips, 0 digital-silence findings, 0 significant clipping findings**, all 23 original slide WAVs untouched. Output `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR223_INDEPENDENT_SIGNAL_SCREEN.json`.
- **No evidence at this stage proves any technical word is mispronounced.** ASR spelling is not a phonetic verdict; acoustic PCM amplitude cannot distinguish homophonic words. Therefore **0 isolated corrections authorized**, no production WAV/MP4 replacement or formal provider selection, no paid calls, and no publication.
- Full HP regression and hosted CI to verify before merger. Continue after this with source-to-video Serway §1.1 completeness/voice-contract integration priorities rather than cycling through inconclusive ASR-only remediation.

## PR #224 — original Serway 1.1 PDF/draft fidelity (31 October 2026)

- PR #223 was fully merged into original MicroGen_AI `main` at `9848b4e0dff5a73aabb7bda6c0d5758df94aa784`; HP full regression 1097 passed, 10 skipped, 162 subtests, four GitHub CI green. Only HP authorized.
- PR #224 branch `feature/hp-pr224-serway-source-draft-fidelity-20261031` based on verified PR #223.
- New `microgen_serway_draft_audit.py` independently checks original 4-page textbook PDF against the *eight-page rendered slide excerpt draft*, including actual extracted PDF text, all 8 source paragraph/page identities, rendered 16:9 title text, Figure 1.1 embedded on slide 5, 2019 SI kilogram warning and official citation on slide 4, source/figure/receipt/slideshow SHA provenance, and write-only-new external output.
- Real Serway source stage with figure evidence: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261029_HP_PR212_PINNED_FIGURE_MAP_CAMPAIGN\1.1`. Actual draft: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261029_HP_PR213_SERWAY_1_1_EXCERPT_SLIDES_V2`. Real external audit: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR224_SERWAY_11_DRAFT_AUDIT.json`.
- Real outcome: all four source pages referenced, eight rendered draft slides verified, source figure and historical SI warning confirmed. **Only 564 normalized quoted characters in 12489 normalized source-text characters (4.516% naive excerpt ratio; NOT academic concept coverage).** Accordingly the current source draft is NOT a full lecture, has no complete narration/WAV/MP4, and is unpublishable.
- Five new focused tests passed: synthetic real PDF/draft verification, forged publication claim, mutated figure, missing figure, no output overwrite. Full HP root regression and four hosted CI must pass before merge.
- Next PR #225 must connect this verified source-draft state to a deterministic, conservative end-to-end production-readiness contract (scope, voice provider and media blockers), avoiding false release and paid/diagnostic Google Cloud voice default changes.

## PR #225 — Serway source-anchored narration/media production handoff (31 October 2026)

- PR #224 verified merged into original MicroGen_AI `main` at `79d277a522eb644c80f9b2f0d6837cf0c7b6d400`; HP root 1102 passed, 10 skipped, 162 subtests, four hosted CI jobs successful.
- HP-only branch `feature/hp-pr225-serway-narration-production-handoff-20261031`.
- New `microgen_serway_handoff.py`: independently replays PR224 real PDF/figure/rendered slide fidelity verification and exactly matches an immutable audit report before creating a *voice-neutral* per-slide narration work order. All eight rows retain source PDF SHA, source page, title, original verbatim excerpt and SI/figure caveats; ungenerated full narration remains `null`, formal voice and WAV/MP4 paths remain `null`.
- Output includes explicit pending dependencies for full source scope, independent automated academic and figure QA, complete narration, production TTS voice approval, source-bound WAVs, video synchronization and independent final acceptance. Google Cloud remains diagnostic-only under owner policy. No paid service or formal default selection is performed; `publication_allowed=false` and no original media is modified.
- Real HP run with current corrected schema: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR225_SERWAY_NARRATION_HANDOFF_V2.json` contains eight source-verified narration anchors and seven pending/unconfigured dependencies; only source-confirmed draft is ready. Focused tests: four new PR225 + five PR224 = **9 passed**. Full HP regression and GitHub hosted CI still required before merge.
- Next work beyond #225: autonomously author and verify *full* source-grounded per-slide narration and figure/math consistency; resolve actual approved production voice/provider without substituting diagnostic Google Cloud; synthesize legitimate full WAVs and synchronized video in output-only stage with independent QA; do not falsely approve unfinished media.
