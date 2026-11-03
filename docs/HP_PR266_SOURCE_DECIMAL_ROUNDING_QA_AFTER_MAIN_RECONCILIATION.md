# PR266 — Source-verified Decimal rounding after safe GitHub reconciliation

## Why this PR uses a NEW number and branch

This work started locally as "PR262" while another authorized development worktree independently merged GitHub PR #262 (PDF regression), #263 (incremental validation), #264 (external voice handoff) and #265 (SHA-bound imported speech WAVs). The original HP checkout still had six local uncommitted rounding-related files. Rather than overwrite any merged work or create a duplicate pull request, we:
- copied the original tracked patch and new Python/test files to a private checkpoint directory;
- preserved the complete dirty working tree in an unpopped Git stash;
- fast-forwarded the current HP worktree from old merge SHA 7556b84 to the latest merged GitHub main 590953da; this separate checkout could not switch to main because another HP worktree already owns the main branch;
- created a clean new feature branch from the updated commit and restored the stashed work with **no merge conflicts**;
- retained existing merged PDF regression, incremental source checks, voice request workflow, and external WAV importer intact.

Private recovery backup: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_DECIMAL_ROUNDING_PRE_REBASE_BACKUP (tracked changes.patch and two untracked Python/test sources). Keep backup until PR accepted. This PR does not modify the other HP worktree or user Chrome sessions.

## Narrow scientific change

New module microgen_private_source_rounding_examples.py implements **opt-in** original_source_decimal_rounding_claims for independently checking explicitly narrated rounding examples. For each claim it:
1. Independently reconstructs original textbook section passages from immutable original PDF, and checks source SHA, section bounds, cited source page, passage IDs and literal anchor.
2. Requires the original unrounded and asserted rounded **number strings** both in the original cited source passages AND in the original voiced narration on that exact slide.
3. Uses Python Decimal (not eval, provider access or locally installed AI model) to round to an explicitly declared 0–6 decimal places using ROUND_HALF_EVEN. It rejects wrong results, unsupported precision, nonfinite or negative/zero values, fabricated source IDs/pages/anchors, ambiguous duplicate claims, and absent spoken evidence.
4. Preserves the printed decimal scale as part of the proof and reports a limited scientific checking receipt; it never claims full physics correctness, mathematical completeness or textbook right-to-publish clearance.
5. Leaves legacy lessons without declared claims unchanged and records zero checks.

Integrated into the existing portable slide renderer (per-slide evidence and total), portable video technical receipt, existing private multi-section scientific audit and PR259 atomic source-coverage/science combined campaign. The same narrowly bounded calculation is reused everywhere; no competing checker or TTS regeneration.

## Real new §1.6 validation after latest main

The original §1.6 source PDF remains untouched:
G:\My Drive\Serway\Serway_1_7\1\1.6\source.pdf
SHA 4045e791d20868b1e492670efa2aeb39455719ffca68c86f27364b122882db40.

Used existing **versioned ChatGPT-authored V5** private narration and source-bounded typed stage from the previously started rounding campaign. Two explicit original-source rounding claims on narrated slide 8:
- 1.346 rounded to 2 decimal places is 1.35.
- 1.343 rounded to 2 decimal places is 1.34.

The original last slide also retains the PR261 rectangular-area significant-figures check (12.71 m times 3.46 m gives 43.9766 m², reported as 44.0 m²).

Re-executed freshly on the POST-SYNCHRONIZATION latest GitHub-main source code. Results:
- 10 authored slide source-and-science checks passed;
- 2 independently verified Decimal rounding examples, 1 source-backed significant-figure area proof;
- completely fresh 10-slide private PDF SHA 8cda876f1b3cac96e964e138f3dd81bab6991ef607243836b2d589a22ac022d7;
- existing atomic source/scientific QA across five Serway sections PASSED; original source PDF hash unchanged; no media assets regenerated or published.

Private stage:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR262_SERWAY16_ROUNDING_TYPED_STAGE
Private new slides:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR266_SERWAY16_REBASED_ROUNDING_SLIDES_PRIVATE
Private new five-section receipts:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR266_FIVE_SECTION_REBASED_SOURCE_SCIENCE_PRIVATE

The previously postflight-verified §1.6 full video is associated with the **original V4 narration**, not the revised V5 rounding narration. It must not be mislabelled as a newly generated or verified V5 video. No new WAV/video publication, formal voice approval, copyright clearance or academic completeness is implied.

## Regression and merge gates

72 focused tests passed after rebasing, spanning rounding, significant-figure precision, unified original-source campaigns, the newly merged external WAV importer and the newly merged incremental campaign. Full HP repository pytest exit 0 and all four GitHub-hosted Windows/Ubuntu Python 3.11/3.12 checks MUST be green on the exact PR head before squash merge. Then sync authorized HP code safely without touching any other worktree.

Owner's permanent policy: original MicroGen_AI development only on HP; generative content only ChatGPT/Gemini, no locally installed LLM (including Ollama/Llama/Qwen), no unapproved paid provider APIs or private textbook upload. Protected textbook assets, private generated scripts/media, and original voices remain on authorized HP. Findings outside this exact supported numeric grammar remain UNVERIFIED rather than triggering broad brittle scientific blockers.
