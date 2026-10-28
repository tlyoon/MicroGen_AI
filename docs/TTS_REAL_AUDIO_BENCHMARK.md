# PR #28: Real WAV pronunciation benchmark

This benchmark uses the actual Thomas Calculus Section 2.5 Slide 10 WAV before and after the lecturer-confirmed Y-letter correction. Audio is not checked into git. Labels and SHA-256 hashes are in `tests/fixtures/microgen_tts_real_wav_labels.json`. Work only with an isolated QA folder, never the original production lesson.

Run `python microgen_tts_benchmark.py tests/fixtures/microgen_tts_real_wav_labels.json --wav-dir "C:\\safe\\staging"`.

Optional `--predictions predictions.json` maps sample IDs to `flag`, `clear`, or `unknown`. Without actual independent predictions, coverage is zero and acceptance fails. Report sensitivity, precision, false-positive rate and unknowns. Two verified labeled samples are a *pilot reference set*, not proof of population-level error performance. Expand only with human-labeled, SHA-matched audio. Neither source nor corrected audio is overwritten.
