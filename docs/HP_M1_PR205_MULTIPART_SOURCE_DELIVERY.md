# HP-only original Section 2.5 multipart A/V evidence acceptance — 28 October 2026

Original MicroGen_AI only; second stacked increment after PR #204. The standard release audit previously rejected a genuinely valid two-part subchapter because the source root lacked a single `slides.mp4`. That was not a missing or broken video: 23 narrated slides had already been split into two real H264/ALAC videos under 600 seconds.

## Reusable source-bound fix

`microgen_multipart_delivery_evidence.py` compares the exact original 23-WAV source inventory with the actual multipart delivery receipt and **separate independently decoded pixel/PCM receipt**. It requires original 23-slide source PDF SHA, source WAV identity for each ordered contiguous slide segment, matching real MP4 hash, assembled WAV decoded PCM SHA and independent MP4 audio decoded PCM SHA, correct 1-based nonduplicated part numbering, exact complete slide coverage, authentic on-disk video files and genuine ffprobe/video stream verification. Each part duration strictly under 600 seconds. Any drift, altered part, missing/duplicated scene, forged prior publication, non-matching audio or overlong part fails closed. This is read-only and never edits video/audio files.

`microgen_tts_release_audit.audit_stage` accepts optional explicit `multipart_receipt` and `independent_av_receipt` **together** as an alternative to a missing single `slides.mp4`. It refuses ambiguous simultaneous single-video and multipart claims. `microgen_tts_quality_campaign` receives corresponding optional CLI flags and records the technical result alongside its original independent acoustic and separate final release checks. Absence of real math and visual semantic proof remains visible: no phonetic, equation or figure-element sync approval is implied.

## Real HP acceptance evidence

Original Thomas Calculus 13e §2.5, 23 slides, 23 current generated TTS WAV files; two source-bound actual MP4s:
- Part 1: slides 1–13, **464.67s**, exact SHA `d7e8ea0ca5a5ec92b3c91211c6aa3042343b67369f6ac99a6d4fd48f5d68d36c`.
- Part 2: slides 14–23, **445.88s**, exact SHA `87fa8e5de978db33bea1efdb80ba6c16a8058e251eac6627558b999662426972`.

Independent MP4 decoded PCM SHA matched each assembled WAV audio SHA. Full 23-slide coverage, exact original slide PDF and WAV sources, correct order, both duration checks. Real QA packet: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_PR205_MULTIPART_REAL_QA`. Final machine gate `video_duration_and_av_integrity=true`, `wav_pcm_integrity=true`, `voice_bound_wav_provenance=true`. Only `independent_acoustic_screen` remains a **technical release** blocker. Source math/figure semantics and genuine narrated equation/figure element synchronization remain unapproved. Publication remains forbidden.

The relaxed media-generation progression in PR #204 continues to allow the workflow without repeated paid speech generation, but is not phonetic acceptance. All original media and historical Google Drive trees untouched. No Dell-115, Yoga6, Zenbook, Whisper, paid AI or public Moodle/YouTube actions.

Focused regression tests exercise valid two parts, missing slide, tampered MP4, altered decoded PCM, forged publication and >=600s duration. Full HP regression and hosted CI on the exact branch must be verified before integration.
