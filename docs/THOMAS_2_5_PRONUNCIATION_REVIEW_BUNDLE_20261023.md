# MicroGen_AI §2.5 — source-bound pronunciation review bundle

On 23 October 2026 the original-package section §2.5 legacy audio was safely recovered into a separate HP-only staging workspace (PR #154) and its original 551.253375-second decoded PCM retained in a 551.25-second lossless technical candidate (PR #155).

This PR introduces `microgen_section25_pronunciation_review.py`, which checks the existing historical QA candidate WAVs before copying them into a **separate comparison directory**. A real read-only pilot created:

`C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_pronunciation_review_PR156`

## Evidence inventory

- Slide 5, `c.` risk: 24 kHz corrective trial; SHA `b446dcb8d90f6b56c3042eb58da0a69a2e8ed76e0e8299faaded126bc5838f3c`. Bound to the current narration sidecar and source video through historical C-dot QA receipt plus per-slide PR39 queue entry. Historical records still say `NOT_REVIEWED`.
- Slide 6, `c.` risk: 24 kHz corrective trial; SHA `b18f87021116042733072ce170fe5fbe47cbdab80d89dfc9a9152e7473aa57d3`. Same historical source/queue binding and review limitation.
- Slide 10, `y-value` risk: 24 kHz trial SHA `fefad11722659354750580bbf73f578281bab96c7803de0328599a3d2f5af5c8`, verified against its QA receipt's current-source-video SHA and proposed replacement SHA; no signed independent listening result.
- Alternative slide 10 PR35 trial SHA `93f11c2c09235b361ebacd967d8bb1136dd70bca02805df2ddd07d52a936cc87` with `ACOUSTIC_QA_UNAVAILABLE` status. Its PR35 receipt **does not independently bind the original §2.5 MP4 SHA**; the bundle retains this weaker provenance flag.

The bundle copies three recovered legacy reference WAVs separately from four candidate WAVs, preserving all SHA digests. It never splices the trials into a lecture, modifies original files, equates a voice name with speaker identity, or declares correct phonetics.

## Remaining completion criteria

1. Reconcile source/voice identity for every proposed replacement and independently verify pronunciation by grounded phonetic observations or listening.
2. Obtain genuine narration-word-to-slide-element alignments, not merely scene timestamps or cue clock guesses.
3. Generate a coherent complete candidate from trusted audio and target PDF using the integrated renderer, with all video parts strictly under 600 seconds.
4. Complete figure/math academic QA and final publishability checks. Do not publish to Moodle or YouTube without full authority and valid release verification.
5. Integrate/review the accumulated stacked PR history before declaring `main` production complete.

Until independently supported, `publication_allowed=false` and no original PDF/MP4/WAV may be overwritten. HP only; no Dell-115/Yoga6, paid provider API, Whisper or GCS distributed lease.
