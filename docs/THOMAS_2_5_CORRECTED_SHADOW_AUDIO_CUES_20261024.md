# Thomas §2.5 — real corrected-WAV acoustic re-timing (2026-10-24)

Original `tlyoon/MicroGen_AI`, HP only. This is a **technical shadow** input for subsequent nonpublishing video generation, stacked on PR #177.

## Failure addressed

The original §2.5 historical narration had per-slide audio timings. Correction trials on slides 5, 6 and 10 have distinct WAV bytes and durations, so simply copying or globally offsetting the original cues is unsafe, even when an older MP4 passed pixel QA.

`microgen_corrected_shadow_alignment.py` constructs a NEW source-hash-bound 17-slide timing manifest. It:
- Verifies original PDF, script, source MP4, recovery WAVs, historical source-bound correction selection, full shadow PCM, and all existing offline ASR reports with their own SHA receipts.
- Allows old recognition only when a slide's WAV SHA remains **identical**. For slides 5/6/10 it **must** use source-bound corrected-trial ASR observations matched by waveform hash, not renamed filename and not old slide clock.
- Requires monotone bounded local word times, measured audio segment duration and global slide start offsets matching the corrected shadow PCM; conservatively selects only unique, high-confidence words in the unchanged original PDF.
- Writes to a new independent output, does not replace the original files, and asserts `phonetic`, `speaker`, `math`, `figure`, and `publication` approvals remain false.

## Real evidence, not simulation

HP-only source data under `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints`:
- Recovery: `2_5_legacy_scene_audio_PR154_v2`
- Historical corrected trial provenance: `2_5_pronunciation_review_PR156` and `2_5_selected_trials_PR168`
- Corrected PCM shadow: `2_5_shadow_pcm_PR169` (552.7095 s including historical tail; speaker unverified)
- Original 17-slide ASR: `2_5_full17_offline_ASR_PR161.json`; corrected-trial ASR: `2_5_offline_vosk_capture_PR158.json`
- New read-only outcome: `2_5_corrected_retimed_cues_PR178.json`: **17/17 slides, 66/66 conservative audio/PDF word cue proposals**, including source-bound, replacement-audio-derived timings for all three changed slides.

| Changed slide | Original recovery scene audio | Historical correction WAV |
|---|---:|---:|
| 5 | 37.200 s | 38.455333 s |
| 6 | 31.800 s | 32.095333 s |
| 10 | 33.000 s | 32.905333 s |

The three corrected WAV SHA values explicitly differ from the original audio; old corrected-slide ASR timings were **not** reused. Model output was previously captured offline and reused only against the same WAV byte hashes; it was not regenerated through a paid service. This is timestamp provenance, **not** independent word/phonetic ground truth.

## Acceptance

Local positive and negative tests cover duplicate/repeated PDF words, low confidence words, altered WAV identity, out-of-duration ASR, missing input, and current-vs-stale cue binding. A correction audio SHA mismatch refuses the manifest before writing. This remains an **unapproved source-bound manifest**, not a final 17-slide corrected video.

**Next independent work unit:** Create an isolated normal-renderer v2 workspace with the actual selected correction WAVs, stage the original 14 untouched WAVs, render from the corrected audio clocks, and verify full MP4 audio fidelity, strict duration and cue pixels. Keep original G: teaching assets, main and historical videos unchanged; no paid API, Whisper, other PCs or publication.
