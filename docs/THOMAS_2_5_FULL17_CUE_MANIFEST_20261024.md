# Thomas Calculus §2.5 — complete 17-slide ASR-to-PDF candidate cue inventory

Original MicroGen_AI, HP-only, 24 October 2026. PR #161, stacked on PR #160.

`microgen_full17_provisional_cues.py` reads the original preserved lesson PDF (17 pages), the checksum-bound provisional scene-partitioned WAV inventory from PR #154, and the offline 17-slide Vosk recognition record. It validates the current original video, PDF, narration and every extracted WAV SHA before matching words.

Real production-input inspection: **17/17 WAVs source-hash verified, 1,179 Vosk-recognized tokens, 66 conservative PDF-word highlight cues** across all 17 slides. Each cue is present exactly once in both the source PDF slide and source-bound speech recognition, with model confidence ≥0.90. Mathematical letters, equations, graphs, ambiguous repeated tokens and out-of-range audio times are omitted rather than guessed. Output: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_cue_manifest_PR161.json` in isolated HP AppData. No PDF/MP4/WAV was modified.

**Scope:** These are recognizer-timestamp proposals, not independently verified phonemes or pedagogically correct formula/figure targeting. The historical AAC/MP4 contains known possible `c.` and `y` pronunciation defects, and the separately preserved ~1.023 s audio tail must be explicitly handled during final composition. Any completed staged MP4 is a technical QA candidate, not a publishable lecture. We need independently supported narration-element timing and phonetic/math/figure quality for final release.

No paid provider calls, Whisper, Dell-115, Yoga6, Moodle, YouTube, or protected main changes.
