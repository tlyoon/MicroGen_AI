# PR #209 — Actual source/WAV-bound figure-reference highlighting

**Original MicroGen_AI, HP only.** Based on code-only merged main `cbe72966709f07fc5d4009681a8c126f4a80fdc9`. No TTS or recognition provider calls, no Whisper, no source folder overwrites, no publication, and no activity on Dell-115, Yoga 6 or Zenbook.

## Previously unresolved visual limitation

PR #198 had real 23-slide WAV-bound word-box highlighting but **zero verified figure-level highlight windows**. This change identifies limited, conservative candidates in actual media rather than inventing equation/figure semantics. It may extend to further sources once enough genuine confidence-bound word evidence is available.

`microgen_single_figure_audio_cues.py` checks the exact prior 146-word source-bound cue manifest, real slide PDF image geometry, source narration text, 23 original WAV hashes, and 23 offline Vosk observation hashes. A candidate is added only when exactly **one embedded image** appears on a slide and both source narration and high-confidence (≥0.9) observed current WAV words explicitly say **curve** or **graph**. Multiple images, generic `line`, low confidence, unavailable timing, missing WAV/ASR and off-page boxes cannot be silently promoted. Every cue and new report preserves `publication_allowed=false` and `figure_semantics_verified=false`.

## Genuine Thomas Calculus 13e §2.5 real HP pilot

- Real source TTS/slides: `20261026_HP_M1_SOURCE_ONLY/2.5`, 23 slides and 23 original WAVs. No source asset changed.
- Original source-bound PDF word cues: 146; augmented: **151** (5 new figure-reference cues on slide **3: 2, 4: 2, 15: 1**). Each corresponds to a real WAV word interval, actual single raster-image box, source narration term and original WAV SHA.
- Figure cue receipt: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_ACTUAL_SINGLE_FIGURE_CUE_PROOF\figure_anchor_cue_receipt.json`.
- Separate new encoded videos: `20261028_HP_M1_FIGURE_ANCHORED_TWO_PARTS`, both under 600 s, 7,285 frames total; duration part 1 **464.67 s**, part 2 **445.88 s**. The videos contain the same original audio source. Active highlighted frames increased from 750 (previous word-only videos) to 776.
- Standard independent A/V technical screen: `20261028_HP_M1_FIGURE_ANCHORED_INDEPENDENT_AV_QA/independent_pixel_pcm_receipt.json`: **23 positive frame checks**, **4 negative controls**, and **full original decoded-audio PCM matches**.
- Separate **actual old-versus-new MP4 frame** contrast tool `microgen_single_figure_frame_diff_qa.py`: requires both MP4 sets, their independent decoded PCM receipts, exact original WAV sources, and pinned cue evidence; at all five spoken-image reference moments the change is localized to the figure box. **5/5 visible incremental overlays**. Figure-box pixel MAE ranged approximately **39–40**, whole-frame change **1.86–2.15**. Actual independent report: `20261028_HP_M1_FIGURE_FRAME_DIFFERENTIAL_QA/figure_frame_difference_receipt.json`.

## Scientifically necessary limits

Five localized image highlight events provide **genuine technical temporal correspondence** between observed words and a displayed image box. They do NOT prove that the image depicts the correctly narrated mathematical concept or that all equation/figure elements are highlighted for the whole lesson. Audio recognition supplies candidate word times, not proven phoneme correctness. `publication_allowed=false`, `full_element_synchronization_verified=false`, and `figure_semantics_verified=false` remain mandatory.

This proof must not be used to bypass the independent acoustic QA or the mathematical-figure semantics acceptance gate. Further generalization should prioritize candidate review and math-element association from actual source evidence over arbitrary timing interpolation. The two older word-only MP4s and all current original WAVs remain untouched.


## Exact source-figure identity hardening (post-initial PR draft)

Independent HP source-image inspection proved byte-for-byte **RGB pixel equality** between the raster image embedded in each highlighted PDF slide and the matching extracted stage image:

| Slide | Pixel-identical source-stage asset | RGB image dimensions |
|---|---|---|
| 3 | `FIGURE 2.34.png` | 238 × 185 |
| 4 | `Figure 2.35.png` | 206 × 137 |
| 15 | `FIGURE 2.44.png` | 220 × 171 |

The tool now **requires an exactly one-to-one pixel-identical original extracted figure asset** before creating any figure reference cue, and saves exact asset SHA-256 in its source-bound cue receipt. A missing asset, two identical assets, any pixel mismatch or ASR/source/WAV/figure mutation suppresses candidates or fails closed. This does not prove that spoken mathematical meaning agrees with the pictured figure.

Updated source-bound pilot `20261028_HP_M1_ACTUAL_SINGLE_FIGURE_CUE_PROOF_V3`: still 3 slides / 5 cues, all matching exact figure assets; `figure_augmented_word_cues.json` SHA-256 exactly matches V2 and the previously encoded two-part candidate MP4s, so expensive media re-render was unnecessary. Updated independent old-versus-new video differential evidence `20261028_HP_M1_FIGURE_FRAME_DIFFERENTIAL_QA_V4` again passed **5/5 actual cue-timed samples** with full audio/MP4 SHA agreement. All original WAVs, PDFs and previous MP4s remain untouched. Final academic/phonetic approval and publication remain false.
