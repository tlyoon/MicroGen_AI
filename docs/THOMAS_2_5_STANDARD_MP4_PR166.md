# Full Thomas Calculus §2.5 standard H.264/AAC technical delivery candidate

MicroGen_AI on HP only, 24 October 2026, PR #166 stacked on #165.

The earlier technical candidate contains all 17 slides, 66 source-PDF word highlights, all decoded original historical AAC audio including its ~1.023-second overhang, in lossless ALAC audio. Some consumer players and video hosts may not support ALAC-in-MP4.

`microgen_section25_distribution_qa.py` creates a **separate** standard H.264 video/AAC 192 kb/s MP4 by stream-copying the previously verified H.264 video and transcoding only lossless audio to AAC. Before accepting the result it checks source and candidate SHA-256, actual output codecs, final strict <600s duration, decoded audio duration against the 551.253375-second original reference (bounded AAC padding), and whole-stream mean loudness drift.

**Real isolated technical result**:
- Output: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_provisional_render_PR162\standard_h264_aac_candidate\section25_h264_aac_192kbps_UNAPPROVED.mp4`
- Candidate SHA-256: `e05685c8499b8daf79cf04a220350380e3abdce455e73ffbaabe3f3d5b550e7a`.
- Duration: **551.25 seconds**.
- Video codec: **H.264**, audio codec: **AAC** (192 kb/s target).
- Relative to original decoded PCM track, AAC output adds **0.042625 seconds** of codec-padding duration; **0.0 dB** mean volume drift under FFmpeg `volumedetect`.
- Every source/original lesson asset is unchanged; no publication action occurred.

This removes the ALAC playback-format concern at a **technical** level. Lossy AAC is NOT sample-for-sample identical, and a successful codec conversion is not independent evidence of correct phonetics, speaker identity, math/figure academic accuracy or exact narration-to-equation semantic synchronization. The original old slide-6 narration still has a model-supported “circa” defect and newer audio trials remain unapproved. Therefore the candidate is named `UNAPPROVED` and `publication_allowed=false`.

Do not publish to Moodle/YouTube or modify the protected original lesson, protected main or any historical media. No Whisper, paid provider API or Dell-115/Yoga6 testing.
