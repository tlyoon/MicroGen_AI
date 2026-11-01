# PR240 — Portable PDF slide and offline lecture candidate pipeline

The original Serway §1.1 fourteen-slide workflow remains untouched. This PR connects the portable, SHA-bound section contract introduced in PR239 to a **separate section-independent teaching-PDF renderer and source-to-offline-video candidate orchestrator**.

## Pipeline

`microgen_portable_slide_render.py` opens an explicitly authorized private `source.pdf`, narration QA, visual plan and portable section manifest. It calls the PR239 independent source-page/topic/adjacent-section audit before creating any media. It renders 2–20 slides with section-specific titles and 2–5 readable bullet points, source-bound narration hashes and optional SHA-locked original figure images specified by filename, slide number, caption and source SHA. For every embedded figure it compares actual PDF image pixels with the original source pixels. Source figures are never resized in-place or modified. Unicode/LaTeX symbols outside the renderer's font capacity are rejected rather than silently corrupted. The original Serway-only SI/figure layout and legacy eight-slide behavior remain available through their previous modules.

`microgen_portable_lecture_pipeline.py` uses one transaction to render a new source-bound candidate PDF, synthesize no-cost offline Piper WAVs in a separate installed environment, verify PCM16 signal and hashes, obtain advisory locally installed Vosk word observations, and FFmpeg-mux a real H.264/AAC MP4. It reopens and compares every video slide's midpoint frame against the corresponding source PDF page, checks A/V duration, keeps voice and textbook model assets outside GitHub and never calls paid cloud TTS. Source/narration/plan/manifest/model and figure SHA snapshots are rechecked before atomically committing the new candidate directory; a failed step rolls back without a completed-looking output folder. Intermediate FFmpeg segments and screenshots are discarded after the video and technical receipt are finalized.

This is **not** an automatic curriculum discovery tool. Manifest topics still need to be source-grounded, but the enumeration itself does not establish completeness or full scientific correctness. Acoustic recognition is advisory and spelling/homophone errors must not initiate endless regeneration. The upstream Piper model's training dataset claim alone does not establish voice-weight redistribution rights. Consequently formal narrator authorization, textbook reuse rights, comprehensive phonetic approval and publication remain false.

## Real test evidence, authorized HP only

- Original Serway §1.1: actual private **14-slide portable PDF**, including unchanged original Figure 1.1 pixels, rendered and verified with a PR239 source-bound manifest at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR240_REAL_SERWAY_PORTABLE_14_PAGE_DECK`.
- A deliberately **synthetic** independent section B.2 (not a real second textbook) with its own three distinct concepts, explicit boundary before B.3 and private original triangle image: a real source-PDF → 3-slide PDF → offline neural WAVs → offline speech recognition → MP4 run succeeded on HP. The first video has duration **136.046 s** from 135.593 s PCM16 audio, SHA256 `a19eed5d155583cc80a80d7d7c94911d4c940285a93f48205aba3592b0a6e504`. The versioned final output uses the cleaned single-MP4 layout.
- Unit tests include source image preservation, figure hash/traversal failure, absent next-section marker, explicit nonformal voice flag, source mutation, mocked end-to-end three-slide transaction, failed TTS rollback, and existing destination refusal. They do not require copyrighted source assets or paid provider calls.

## Required next milestone

Generalized composition is demonstrated, but academic coverage contracts remain provided by an earlier source-specific analysis. The next meaningful acceptance target is a **fully authorized second real textbook subsection**, using its actual source pages, figure mappings, complete topic coverage and expert-independent mathematical QA to exercise the portable pipeline. Do not call the synthetic B.2 example a published lecture or a second real textbook.

## Final cleaned real candidate

The second versioned synthetic B.2 run on authorized HP produced an independently synthesized, actual **135.661 s** three-slide H.264/AAC MP4 from **135.615 s** of no-cost PCM narration with 3/3 actual decoded frame/pixel checks. Its private path is `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR240_PORTABLE_B2_VIDEO_VERIFIED_V3\video\lecture_portable_neural_candidate.mp4`, size 1,999,101 bytes, SHA256 `945458e8548f79743392a13ecc5759248584808e90979a101f13c5c4b0d6e2be`. The final folder includes source-bound independent academic report, 3 PCM files, offline ASR advisory and media receipt; FFmpeg scratch files are absent. This synthetic proof does **not** constitute a second original textbook study or a formal narrated release.
