# PR #188 — Independent corrected 66-word video pixel/timing QA

**Project:** original tlyoon/MicroGen_AI, not MicroGen_AI_Web.
**Base:** stacked draft PR #187 head `fdf7c0d72d00b66ca890e25909a9569ef7008923`, hosted GitHub CI 4/4 SUCCESS.
**Only physical device:** Dell-115. No HP, Yoga 6, Zenbook, Whisper, paid speech service, protected-main merge, historical G: teaching media modification or publication.

## Real Section 2.5 technical evidence

The new `microgen_corrected_word_pixel_qa.py` independently rasterizes each of the *original* 17 source-PDF pages, reads the current 17 corrected WAV/ASR/PDF SHA-bound 66-word cue candidate manifest, and verifies the exact full-corrected-PCM video receipt. It then independently decodes the actual 8-fps MP4 at every source-bound cue's encoded frame center, measuring the RGB absolute difference **inside** the cue's PDF box and **outside all simultaneously active boxes**. It also tests the cue ROI after each word expires, where sufficient same-slide frames exist.

Real video: `20261024_Section25_REAL_PILOT\corrected_asr_word_video_v1\section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4`, 552.75 s with bit-identical complete corrected shadow PCM, including source AAC tail, 66 candidate cue boxes from genuine fresh Vosk timestamps.

The development audit was deliberately fail-closed:
1. Original read-only audit `corrected_asr_word_pixel_audit_v1`: 66 active cue samples and 66 adjacent post-cue tests; three failed controls (all in post-cue regions), `NEEDS_REVIEW`. No approval inferred.
2. Inspect failure: near the first two cue ends, FFmpeg seek to the immediately adjacent 8-fps time can return the previous highlighted frame. The audit now demands **one full frame = 0.125 seconds** after cue expiry before using a post-cue control. Audit `corrected_asr_word_pixel_audit_v2`: 66 positives, 64 controls, one low-value codec difference 4.149 (threshold was 4.0).
3. **Independent calibration:** at 425.1875s for slide 14 word `evaluate`, the already technically verified **unhighlighted** video differs from source PDF in the same ROI by 4.078 mean RGB units, while highlighted video differs by 4.149, with direct highlighted-vs-clean ROI difference 1.707. The difference is codec noise, not persistent yellow highlight. Use a conservative 5.0 post-cue MAE limit, far below representative active overlay differences such as 53.83 on slide 1.
4. Final new read-only audit `corrected_asr_word_pixel_audit_v3`: **66/66 positive cue samples + 64/64 post-cue controls passed, zero failed, zero cues lacking an encoded frame center**. Two post-cue controls are unavailable inside their slide intervals under the safety guard; this is **not** a continuous-time guarantee. Receipt status `CURRENT_ASR_OVERLAY_PIXEL_AUDIT_TECHNICAL_PASS`, with `publication_allowed=false`.

All three audit reports remain separately preserved for review. No original/current source videos were overwritten, and no other device was used.

## What is and is not accepted

- Technical **PDF word box display at selected ASR timestamps** and delayed no-longer-active controls: pass, limited by 8-fps frame quantization and FFmpeg screenshot seeking.
- Independent verification of the **spoken word identity**, speaker, mathematical equation semantics, correct figure/narration correspondence, and listening quality: **NOT done**.
- Technical video duration and complete decoded source PCM already verified by earlier stages, unchanged.
- Publishing or promotion: **prohibited** until final QA/owner authorization.

The new unit tests mock decoder captures to verify true positive boxes, negative control disappearance, missing overlay detection, source/video/cue fingerprint changes, forged approvals, output collision and no-frame cue failure. No screenshot mock is counted as real textbook acceptance.

**Next:** independent math/equation/figure semantic QA and reliable phonetic c/y listening; then consider release only after those approvals. Do not generate a "publishable" flag from this strictly technical pixel QA.
