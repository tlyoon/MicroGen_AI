# Thomas Calculus §2.5: full 17-slide technical video with preserved original PCM

Original MicroGen_AI on HP, 24 October 2026. PR #163 stacked on #162.

The previous full-lesson renderer produced 17 source-PDF slide images with 66 conservative audio-derived text highlights and a combined MP4 under ten minutes. Its AAC-per-slide composition omitted the separately preserved audio after the historical MP4 endpoint.

The new `microgen_full17_pcm_mux.py` validates source-PDF/narration/MP4 checksums, the prior 17-slide technical part, and the 17 reconstructed WAV clips plus source AAC tail. It constructs a lossless PCM master identical to the original historical MP4's decoded AAC audio (sample-for-sample SHA-256 equality), then replaces the preliminary part's AAC with this master using ALAC lossless while extending the last slide.

**Actual verified result:** `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_provisional_render_PR162\complete_decoded_pcm_candidate\section25_full17_ASR_HIGHLIGHTS_ALAC_QA_ONLY.mp4`.

- Video duration: **551.33 seconds**, strictly less than 600.
- Full source decoded PCM including last **1.023375 seconds** preserved exactly: **PASS**.
- Candidate MP4 SHA-256: `3c720f72772e4b67453173aeea9dbdc330062800ec46185b7d0ae80187bdf2ec`.
- All 17 PDF pages from the original and 66 conservative ASR-to-word cues were used in the staged render.
- ALAC MP4 is **technical QA only**; player/distribution compatibility and publishing are not certified.
- Prior original source PDF, historical MP4, narration, old individual WAVs, protected main untouched.
- Historical audible defects such as slide6 “circa” have **not** been corrected, because replacing only some WAVs without reliable voice, phonetic, semantic and duration evidence would create an unsupported final product.
- Complete mathematical formula/figure-to-narration synchronization is **not** verified. Recognizer-suggested timings are not phonetic ground truth.

Next stages: independent pixel review on the final combined MP4; figure/equation semantic alignment; pronunciation correctness and voice integrity QA; release acceptance gates. No Whisper, paid API, Dell-115, Yoga 6 or publication.
