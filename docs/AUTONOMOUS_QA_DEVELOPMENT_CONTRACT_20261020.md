# MicroGen_AI Development & QA Contract — Autonomous Progression (2026-10-20)

**Status: authoritative for current MicroGen_AI TTS development and QA, superseding any earlier mandatory manual-approval instructions for this pipeline.** This is the *original* MicroGen_AI project, not MicroGen_AI_Web.

## User-directed policy
- No human approval, listening confirmation, academic sign-off, figure sign-off, element-highlight sign-off, reviewer signature or manual QA checkpoint is required to **develop, test, open draft PRs, continue automation, or evaluate technical release readiness**.
- Machine tests and evidence decide progression. The default QA policy is `autonomous`. A separate `human-certified` mode is available only if someone explicitly requests formal human certification; it is **not a prerequisite**.
- Corrections discovered later can be submitted as new isolated PRs and regenerations without erasing earlier provenance or claiming the earlier output was correct.

## Mandatory technical safeguards — NOT waived
1. Verify narration mathematical preflight and approved context-sensitive speech normalization.
2. Verify the WAV-to-script binding, **same pinned provider and voice**, source and media SHA-256, slide count and monotonic positive audio timing.
3. Inspect actual WAV PCM integrity; digital silence, major clipping or invalid frames must block.
4. Obtain **genuine independent acoustic evidence** when a candidate requests pronunciation-screen clearance. Provider outage, unverified transcripts, word discrepancies or inconsistent evidence **remain technical blockers**, not auto-pass. ASR agreement alone cannot prove a difficult phoneme.
5. Enforce every rendered lecture video **strictly under 600 seconds**, splitting longer topics, and ensure full media A/V integrity.
6. Retain scholarly/figure correctness and narration-to-element highlighting as **quality objectives**. Do not present technical checks as certification of those properties where automated semantic/visual tests do not yet exist. Record unverified dimensions explicitly and continue developing automated validators.
7. Never touch production source media or original dirty worktrees from QA scripts. Use isolated work directories, preserve old WAV/MP4 and rollback evidence, protect main, do not publish to Moodle automatically from the read-only QA command, and continue Dell-115-only testing for the present campaign. No Whisper, no GCS distributed lease.

## Outcome language
- `automated_technical_qa_passed=True`: all **implemented mandatory technical** gates passed. This is enough for unattended development progression and eligibility for a separately controlled promotion step, with no human-review prerequisite.
- `human_qa_certified=False`: no signed human review occurred; this is normal and **not a blocker** under `autonomous`.
- `unproven_quality_dimensions`: any phonetic precision, mathematical soundness, complete figure quality, and element-level synchronization not objectively verified by current automation must remain disclosed, **not silently marked passed**.
- `ready_for_separate_promotion=True`: indicates eligibility **only**; QA evaluation never performs publication, creates reviewer signatures, bypasses technical blockers, or modifies the original lesson.

## Commands
```
python microgen_tts_release_audit.py QA_LECTURE_STAGE --qa-policy autonomous
python microgen_tts_release_audit.py QA_LECTURE_STAGE --qa-policy human-certified
```

The former is the default. The latter is voluntary and requires genuinely trusted signed reviews. The one-command QA packet creates a complete review queue for optional spot-checking and troubleshooting, not as a release requirement.

## Scope and remaining implementation work
Historical legacy promotion coordinator paths still contain their own reviewer phases and do not automatically inherit the new API; migrate those separately with regression evidence **before** deploying this contract to them. Likewise, new automated figure, academic and individual-element highlighting validators are needed before claims of fully verified scholarly video quality are justified. This contract does not retroactively validate or publish pre-existing Thomas Calculus files.

## 30 October 2026 owner TTS provider amendment — authoritative override

The owner now **permits Google Cloud Text-to-Speech for troubleshooting** (short pronunciation/voice/provider diagnostics), including legitimate limited chargeable API usage. It **must not remain the implicit default for formal lecture TTS**. Formal TTS defaults to `MICROGEN_FORMAL_TTS_PROVIDER=unconfigured`, deliberately refusing new WAV synthesis until an approved provider is explicitly selected. Presence of Cloud credentials, legacy Chirp WAVs or a configured voice name does not confer formal production authorization. See `docs/OWNER_TTS_CLOUD_TROUBLESHOOTING_AMENDMENT_20261030.md` for controlling diagnostic limits, separate CLI, nonpublication, account/cost and provenance safeguards. The HP-only owner device amendment remains governing; any earlier Dell-only text above is historical.
