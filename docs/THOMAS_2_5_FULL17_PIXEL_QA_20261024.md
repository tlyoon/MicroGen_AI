# Thomas Calculus §2.5 full video — all 66 timed overlays independently verified

Original MicroGen_AI, HP only, 24 October 2026; draft PR #164 stacked on #163.

`microgen_full17_pixel_acceptance.py` verifies visual timing on the **final combined lossless 17-slide video**, not isolated individual-slide demonstrations. It reads the source and completed candidate receipt, confirms the original PDF and final MP4 SHA hashes, replays each of the 66 conservative source-PDF word cues using the measured per-slide video clock, extracts frames just before and during each cue and measures pixel changes inside the source PDF word rectangle.

**Real result: 66 cues checked, 66 visible on-screen highlights detected, 0 missing cues.** Report: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_all_cue_pixels_PR164.json`, status `ALL_VISUAL_CUES_VERIFIED`. The complete candidate MP4 is still `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_provisional_render_PR162\complete_decoded_pcm_candidate\section25_full17_ASR_HIGHLIGHTS_ALAC_QA_ONLY.mp4`, SHA `3c720f72772e4b67453173aeea9dbdc330062800ec46185b7d0ae80187bdf2ec`, duration 551.33 s. All decoded original AAC PCM samples, including the ~1.023 s tail, remain preserved.

This verifies physical on-screen pixel changes at the **ASR-assigned time**, but not authenticated spoken phonemes, correct teaching semantics, expected highlighting of the actual relevant equation, diagram or figure. Audio still contains historical pronunciation defects, including strongly indicated “circa” on slide 6. Therefore `publication_allowed=false` and mathematical/phonetic/voice QA remain blocked. No original files or protected main changed, no paid API, Whisper, Dell-115 or Yoga 6.
