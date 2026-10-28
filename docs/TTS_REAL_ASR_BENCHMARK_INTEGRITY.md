# PR #50 — Grounded real-audio benchmark and source isolation

Adds fail-before-inference budgeted checks for the two-model human-labeled WAV benchmark, including SHA-256 integrity, request-count and input-audio-duration caps. Source files are SHA checked **again after** all model calls; if a recognizer or a concurrent process modifies audio during the run, no score is emitted. Reports must be NEW paths outside the source WAV tree, never overwritten.

The user-confirmed Thomas §2.5 original-vs-corrected Slide 10 reference dataset is used for the Dell-115 pilot; source raw WAVs stay unchanged.
## 2026-10-20 Dell-115 real-audio trial (not committed WAVs/transcripts)

- Reference set: Thomas Calculus §2.5 Slide 10, 2 real SHA-bound WAVs (reported defective Y→yay; lecturer-confirmed corrected Y→why)
- Two genuine model attempts: `gemini-3.5-flash` and `gemini-3.8-flash` via script-blind audio transcription. The latter was unavailable; the benchmark correctly produced **0 scored coverage** and **2 UNKNOWN cases**, not a false pass.
- First recognizer's transcripts contained two `y-value` spellings for **each** WAV, including the known defective pronunciation. This demonstrates that normalized ASR text can hide the audible letter-name error, even where a recognizer returns otherwise plausible output.
- Resource preflight recorded 4 planned model requests and 132.101333 input audio seconds (not a billing estimate). The full raw report is retained only in Dell-115 scratch at `microgen_pr50_live_y_benchmark_20261020.json`; no audio, transcript or keys are included in Git.
- No general sensitivity, specificity or near-zero pronunciation-error claim can be drawn. Another machine-calibrated phonetic method or model pair is required for this error family; never fake human listening approval.
 A clean text transcript may still hide a phonetic defect, so these metrics are an ASR proxy **not** an independent hearing certificate. An inconclusive or unavailable model result remains UNKNOWN and never fabricated as success.
