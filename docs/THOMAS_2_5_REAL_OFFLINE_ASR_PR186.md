# PR #186 — Reproducible offline corrected speech recognition, Dell-115

**Project:** original tlyoon/MicroGen_AI, NOT MicroGen_AI_Web.
**Base:** latest verified open draft PR #185 head `edf5b4660ca4c201eb626ce3de22cb4b67c721ab`. Its 4/4 GitHub-hosted CI passed.
**Device:** Dell-115 ONLY. No HP, Yoga 6, Zenbook or changes to protected main or historical G: media.

## Recovery result: genuine textbook-derived corrected Thomas §2.5

- Previous real corrected stage is in the separate AppData campaign `C:\Users\tlyoon\AppData\Local\MicroGen_AI_Checkpoints\20261024_Section25_REAL_PILOT`.
- A *free* optional Vosk Python runtime (vosk==0.3.45) was installed in an isolated Dell-115 environment `C:\Users\tlyoon\AppData\Local\MicroGen_AI_Tools\vosk_env`. This DID require a third-party open-source Python package download; no AI APIs, paid tokens or Whisper were used. No main/base Conda packages changed.
- The official offline `vosk-model-small-en-us-0.15.zip` model (41,205,931 bytes) was downloaded to a separate local tools directory, independently SHA-256 verified against the publicly published file digest `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`, then safely extracted. No model or weights committed to GitHub. Apache 2.0 model, as listed on the official Vosk models site.
- New `microgen_local_vosk_model_verify.py` contains the pinned digest and bounded, zip-slip/symlink/duplicate-safe extraction; it never downloads anything by itself.
- New `microgen_resumable_corrected_asr.py` binds each current WAV SHA, source PDF/script SHA, full stage timeline and acoustic-model tree SHA to each observation before writing a per-slide immutable checkpoint; verifies all model and source hashes after every slide. Run with max-new-slides=3 produced three authentic slide records; a **separate** resume processed slides 4–17, without repeating the first three.
- Real corrected 17/17 Vosk observations recorded at `corrected_vosk_asr_progress\asr_current_audio.json`; **1,178 observed model words**, **1,043 with confidence ≥0.90**. These are ASR hypotheses, not human-validated transcripts.
- The existing PR #178 `microgen_corrected_cue_realign.py align` was executed successfully against those **current** 17 WAVs. It created `corrected_stage\cues.json` with **66 new unique high-confidence PDF text candidates** distributed across all 17 slides. Manifest SHA-256 `bf5c41dfd2480e1220d03f0f6ddb02640ea1a18b65fd0d532d64108be275832f`. The numerical coincidence with an old 66-cue historical run does **not** mean old timestamps were reused: the new manifest's derivation is `CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH`, and all audio bindings have verified current hashes.
- On slide 5 and 6 Vosk recognized the variable `c` as `see` or `sea`; on slide 10 it recognized `y-value` as `why value`. These observations are *consistent with* letter-name pronunciations, but **cannot independently prove** that the perceived `circa` defect is absent or narrator identity is consistent.

## Safety limits and next milestone

- Existing slide-corrected, PCM-identical **552.75-s** technical video with **50/50 PDF slide pixel** observations was created by PRs #182–183 *before* new word-cue overlays. The new 66 candidate word cues have **not** been rendered to new highlighted video or independently assessed for text/figure pixel correctness.
- No scientific/math expression semantic QA, one-speaker identity, independent acoustic/listening approval or publication release is implied. `spoken_word_alignment_verified=false`, `mathematics_semantics_verified=false`, `publication_allowed=false` remain mandatory. Existing source PDFs, production MP4s, historical WAVs and published materials remain unchanged.
- `microgen_resumable_corrected_asr.py` returns exit code 2 on candidate completion *on purpose*, to avoid conflating success of model observation with publication approval.
- Next safe development work: render isolated corrected **cue-highlighting technical candidate** against exact full corrected shadow PCM and **current** PDF geometry; inspect actual cue transitions with source-bound screenshots, word/figure semantic and phonetic QA independently. Never replace the verified no-highlight MP4 or auto-publish.

## Dell-only repeatable local invocation

In PowerShell, from a clean checkout of the stacked PR, set `$env:PYTHONPATH` to the isolated Vosk runtime's `Lib\site-packages` and run `microgen_resumable_corrected_asr.py` with explicit `--stage`, `--model`, `--ffmpeg`, `--progress` and `--max-new-slides`. Reuse an existing progress directory only when all source+model SHA checks pass. A completed run refuses to overwrite itself. Run `microgen_corrected_cue_realign.py align --stage ... --recognition ...` once against an unused `cues.json` path. This code performs no downloads itself.
