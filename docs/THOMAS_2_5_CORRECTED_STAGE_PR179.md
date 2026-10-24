# Section 2.5 source-safe corrected 17-WAV stage (PR #179)

This unit completes the *staging prerequisite* for PR #178's offline
recapture/regeneration. It operates only on the original MicroGen_AI package,
does not change the original lesson, and never treats corrected historical
trials as acoustically approved production speech.

## Inputs and resulting stage

`prepare_section25_corrected_wavs(recovery, selection, new_stage)`
requires:
- Source-verifiable original `recovery/workspace_receipt.json` and
  `recovery/legacy_mp4_audio_receipt.json` (17 recovered source clips,
  original MP4 SHA and source PDF/script fingerprints).
- The selected historical speech trials' unchanged
  `selection/selection_receipt.json`, with exactly slides 5, 6, 10
  (CDOT, CDOT, Y_VALUE). All three trials must retain unapproved status,
  explicit slide and WAV SHA, and the verified selected path.
- A completely unused *external* destination, outside recovery, selected
  corrections, original teaching folder, protected originals and any parent
  directory of those paths.

All 17 WAVs are verified for original/trial identity and bounded duration
**before** a new stage is created. Selected correction WAVs are copied for
slides 5/6/10; the other 14 recovered original WAVs are copied unchanged.
Every copy and both receipts are re-hashed after copying; unexpected source
mutation destroys only the newly owned stage, never original files. A new
inventory and measured full-lecture timeline are generated and must be
**strictly under 600 seconds**.

Old `cues.json` is never copied. The stage emits
`corrected_stage_receipt.json` with `fresh_offline_recognition_required=true`,
all prior cues invalidated, and `publication_allowed=false`.

The historical source AAC overhang is **not** silently embedded in one
slide; it remains a separately documented mastering obligation for a later
corrected full-video candidate.

## Limitations / actual tests

- This PR does not prove good c./y pronunciation, independent voice identity,
  true word alignment, formula narration, correct figure reference, listening
  QA or release readiness. Trial audio is explicitly UNAPPROVED.
- Synthetic 17-slide fixtures exercise original and changed WAV checksum
  checks, new cumulative clocks, corrupted/duplicated correction selections,
  source MP4 identity, unsafe 600-s duration, destination collisions, and
  source or selection receipt changes during copying. The fixtures do NOT
  substitute for the real textbook/audio.
- Dell-115 only for local work; no HP/Yoga6/Zenbook access, model download,
  paid API, Whisper, production source edit or publication.

## Next real acceptance step

Stage actual source-verified §2.5 historical clips using this function into
an independent Dell-only workspace, then run PR #178 `capture` with an
already-installed Vosk model and `align`. Check the current 17 audio SHA
and new word clock and independently verify phonetic and mathematical
semantics. Any missing original real media, model or expert phonetic evidence
remains an explicit blocker; do not invent it.

Read `docs/CONTINUATION_CHECKPOINT_LATEST.md` and check latest live PR/CI
and owner processes again before any further code change.
