# PR269 — automatic chapter WAV capture and single readiness report

## Goal

Finish the last deterministic integration step between PR267's complete source/science/voice request handoff and PR268's source-verified private chapter video assembly. There must be NO manual entry of WAV SHA256 values, and a missing WAV must give ONE consolidated chapter-wide report, not cause recurring individual-PDF fixes. No synthesis, paid API, local language model, voice selection, or publication.

`microgen_private_chapter_capture_discovery.py` accepts an unchanged PR268 private blank source-bound chapter plan, PR267's original complete chapter handoff, and an **existing private WAV-drop root**. It checks original source PDF/narration/slide SHA identity, exact expected section and slide filenames, WAV PCM structure and SHA, then uses the established PR265 per-section capture validator. A complete set with explicitly and truthfully labeled provider/voice values produces SHA-populated manifests and a PR268-compatible capture plan **atomically**. An incomplete set produces only a private JSON readiness receipt with all missing/invalid/unexpected WAV names, not partial approved manifests.

Provider labels supplied by the owner are a *declaration only*, never independent provider authentication or voice authorization. The waveform-to-spoken-words identity, pronunciation, narrator rights, academic approval, copyright, and publication release remain unverified even if file hashes and MP4 frame alignment pass.

## Real Serway Chapter 1 current checkpoint

Original immutable six-section bundle:

`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR267_SERWAY1_SIX_SECTION_REAUDITED_VOICE_PRIVATE`

PR268 source-bound blank plan:

`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR268_SERWAY_CHAPTER1_SOURCE_BOUND_AUDIO_PLAN_V2_PRIVATE.json`

The owner-private WAV drop (empty and ready for authorized files):

`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR269_SERWAY1_EXTERNAL_WAV_DROP_PRIVATE`

It contains six directories `section_1_1` through `section_1_6`. Put only the matching `slide01.wav`, `slide02.wav`, ... (exact, no extra WAVs) in each corresponding folder after producing or obtaining the **authorized** original source-matched speech. Do NOT substitute old local diagnostic candidate WAVs as formal voice; old section 1.6 recordings can correspond to V4 narration, while current Chapter 1 material contains later typed rounding content.

The no-assumption provider-label template, all values initially null:

`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR269_VOICE_DECLARATIONS_TEMPLATE_PRIVATE.json`

Provider and voice should be filled by the person who actually authorized and obtained the new recordings; changing labels does not authorize provider usage. The current real private inventory, obtained with no actual WAV production:

`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR269_REAL_SERWAY1_AUDIO_READINESS_PRIVATE\chapter_capture_discovery_receipt.json`

Real result: **six sections, 57 WAVs expected, zero WAVs supplied, 57 absent, zero ready capture manifests, publication false, zero new provider/model calls.** No legitimate completed Serway1 MP4 can be generated from absent audio.

## Usage once approved recordings are supplied

With the repository environment active, and private paths substituted as needed:

```text
python microgen_private_chapter_capture_discovery.py \
  --chapter-bundle PRIVATE_PR267_CHAPTER_BUNDLE \
  --blank-input-plan PRIVATE_PR268_V2_SOURCE_PLAN.json \
  --wav-root PRIVATE_PR269_WAV_DROP \
  --declarations OWNER_COMPLETED_PRIVATE_PROVIDER_LABELS.json \
  --new-private-output FRESH_PRIVATE_DISCOVERY_OUTPUT
```

If WAVs are missing, read the ONE `chapter_capture_discovery_receipt.json`; output deliberately has no `capture_plan_ready.json`. Once all are validated, the fresh output has the automatic `capture_manifests/section_1_*.json` and `capture_plan_ready.json`. It can be directly passed to the previously merged video assembler:

```text
python microgen_private_chapter_audio_video.py \
  --chapter-bundle PRIVATE_PR267_CHAPTER_BUNDLE \
  --capture-plan FRESH_PRIVATE_DISCOVERY_OUTPUT/capture_plan_ready.json \
  --new-private-output FRESH_PRIVATE_VIDEO_OUTPUT \
  --render-private-videos
```

That produces six individual PRIVATE, NON-PUBLISHED MP4 candidates, one per Serway chapter section, and independent PDF midpoint frame QA receipts. It does not certify acoustic words, narrator ownership or release rights. Once real audio is present, an independent listening and rights/academic review must occur before any publication or combined course release.

## Acceptance

Synthetic test suite covers missing, extra, misnamed, corrupt and edited files; missing or forged provider declarations; changed original source PDF; changed input plan; race/atomic rollback; and actual two-section WAV capture -> PR268 intake -> FFmpeg source-verified MP4 assembly. No textbook narration, source pages, speaker model, paid provider token or private WAV included in public GitHub.

Full HP root pytest and all four hosted GitHub Linux/Windows Python 3.11/3.12 jobs on exact PR head are required before merge. After this milestone do not add more per-PDF science QA fixes unless a shared blocker genuinely regresses; any remaining formal-audio procurement is a real external approval/input dependency, not code failure.
