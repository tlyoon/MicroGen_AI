# PR #222 — source-bound technical-pronunciation listening excerpts

**Scope:** Original MicroGen_AI. HP-only local execution. Not MicroGen_AI_Web.

This feature turns the previously saved, approximate offline Vosk timing suggestions
into **source-preserving external PCM audio clips**. It does not detect phonetic
identity independently, conclude a voice is mispronouncing a word, select a formal
provider, or authorize video publication.

## Pre-existing required evidence

- Original lesson stage with `script_tts.json`, verified per-slide `slideN.wav`,
  and its provider provenance manifest.
- Corresponding independently saved, per-slide offline ASR reports
  `slide01.json`, etc., each bound to the exact source WAV SHA-256.
- The immutable saved post-TTS pronunciation evidence receipt.
- The immutable **PR #221** candidate timing-index report, derived from that
  very same original source and offline ASR evidence.

The tool independently rebuilds the timing index against every source
WAV, ASR receipt, narration and provider manifest. Any stale/tampered receipt
is rejected; mere matching filenames are insufficient.

## HP invocation

From the original MicroGen_AI repository:

```powershell
python microgen_tts_candidate_clip_bundle.py `
  --stage "<HP-original-stage-directory>" `
  --asr-dir "<HP-offline-ASR-reports-directory>" `
  --evidence "<HP-immutable-evidence.json>" `
  --timing "<HP-immutable-PR221-timing.json>" `
  --new-output "<fresh-HP-external-output-directory>"
```

An output folder must not exist beforehand and must not be in the
original source tree, the ASR source tree, or the protected `My Drive`.
The procedure creates a temporary isolated sibling and only renames
its fully validated output into place. It never overwrites prior receipts.

By default, at most 16 technical-word candidates are accepted. Each clip
is bounded to 5 seconds, using up to 0.35 seconds of surrounding context
on either side; all clips combined may not exceed 60 seconds. Identical
recognized phrases with non-unique ASR locations are skipped, while
overlapping candidate time windows are refused rather than guessed.

## Output and result interpretation

Each clip has a source slide, expected mathematical wording, unverified
recognition, original WAV SHA, saved ASR-report SHA, exact excerpt SHA,
ASR confidence floor and approximate timing. `review_index.json` declares
`review_status: UNREVIEWED`, `phonetic_identity_verified: false`,
`publication_allowed: false`, and zero provider calls.

**Real Thomas §2.5 HP verification (31 October 2026):**
11 clips on 8 slides, 16.609 seconds total, all 11 clip checksums
reverified, and all 23 original slide WAV SHA-256 values verified unchanged.
The source, voice and academic content have not been approved.
The real output lives in
`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR222_THOMAS25_TECHNICAL_AUDIO_CLIPS`.

A recognizer spelling such as `cosine -> coast sign` may reflect an ASR
homophone approximation rather than wrong spoken audio. It cannot alone
justify regeneration. Genuine defects require independent corroboration
and fresh downstream audio QA in a separate, source-preserving workflow.
