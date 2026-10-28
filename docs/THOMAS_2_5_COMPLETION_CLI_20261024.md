# Source-safe reproducible §2.5 technical completion CLI, 24 October 2026

PR #165 (original MicroGen_AI, HP only) adds `microgen_section25_completion_cli.py`, an authoritative programmatic entry point for the real pipeline developed in PRs #161–#164.

Invoke with Python:
- `python microgen_section25_completion_cli.py prepare --manifest <source-bound-17-slide-ASR-cues.json> --stage <new-independent-HP-folder>`
- `python microgen_section25_completion_cli.py render --stage <folder> --ffmpeg <ffmpeg-executable>`
- `python microgen_section25_completion_cli.py pcm --stage <folder> --ffmpeg <ffmpeg-executable>`
- `python microgen_section25_completion_cli.py pixels --stage <folder> --ffmpeg <ffmpeg-executable> --pixel-report <new-report-path>`
- `python microgen_section25_completion_cli.py audit --stage <folder> --pixel-report <report-path>`

Each workflow phase refuses overwriting earlier outputs and checks the original lesson SHA receipts. The `audit` phase returns nonzero **2** when external release QA is unresolved, rather than reporting a successful technical render as a publishable lecture.

**Real original §2.5 audit result:** all 17 slides rendered, 551.33-second final MP4, all 17 historical PCM-derived audio samples preserved exactly (including the additional 1.023375-second tail), and 66 of 66 source-grounded text highlights verified by individual before/during frame pixel checks. Candidate SHA-256: `3c720f72772e4b67453173aeea9dbdc330062800ec46185b7d0ae80187bdf2ec`.

**Still blocked:** genuine spoken-word-to-equation/figure timing and pedagogical semantics; independently certified mathematical figure/content quality; correct `c.` and `y` pronunciations with authenticated speaker consistency; independent transcript/listening quality; recognition timestamps as independent ground truth; consumer distribution compatibility of lossless ALAC MP4; and review/integration of stacked draft PRs. The original recovered historical track notably has three model-recognized “circa” occurrences on slide 6. No real correction audio has been promoted.

The technical media itself is complete, but the MicroGen_AI project is **not yet fully certified, merged or publishable**. This CLI is deliberately source-safe and contains no publication action. Do not publish to Moodle or YouTube, edit protected original G: Drive lecture assets, call paid APIs, install Whisper or involve Dell-115/Yoga6 without changing the project constraints.
