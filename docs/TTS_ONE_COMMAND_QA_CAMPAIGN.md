# PR #39 — Single-command, read-only MicroGen TTS QA campaign

`python microgen_tts_quality_campaign.py ISOLATED_LECTURE_DIR NEW_QA_OUTPUT_DIR` generates a complete, immutable-for-that-run **non-published QA packet**. The command checks all original narration and slide WAV hashes, measures slide timing and per-WAV structural quality (PR #37), produces source-based pronunciation risks, creates SHA-matched short review clips (PR #30), makes an all-slide listening queue (PR #38), and runs the release-evidence audit (PR #32/#33/#36). It refuses an output path inside the source tree or one already occupied, and checks original file hashes both before and after packet generation.

The packet contains source hashes, pronunciation risks, PCM metrics, clip manifest, listening checklist, and all outstanding release blockers. Completion of this command means **only that review data was generated**. It never calls paid TTS/ASR, fabricates phonetic success or signs reviews, writes to Moodle, promotes an MP4, or copies over historical media. A future independently controlled review system must conduct signed listening/academic/figure/highlight review and genuine audio recognition before release.

Run with the real Section 2.5 PR #35 scratch output for an integration pilot; the expected result remains unpublishable even though the review video is under 600 seconds.
