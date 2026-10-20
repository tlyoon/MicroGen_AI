# PR #51 — Automated model-pair calibration against confirmed Y pronunciation defect

MicroGen now supports optional strict **machine** calibration of an audio-recognizer pair against SHA-verified real before/after WAV references. A successful result must explicitly identify both the historical **yay** error and the corrected **why** letter-name reading using two distinct models, with 100% observed coverage and no missed or false alarms in this tiny labeled set. The validator independently recalculates classifications and metrics from saved transcripts, matches all sample hashes and enforces the exact configured model identities. Incomplete/UNKNOWN reports fail; no human approval is requested.

### Observed live failure
The October 20, 2026 Dell-115 dual-model pilot was NOT calibrated: `gemini-3.8-flash` was unavailable, and `gemini-3.5-flash` rendered both bad and corrected audio in normalized text as `y-value`. This gives **zero scored coverage** for the pair, not evidence that either recording was correctly pronounced.

### Application
In the unattended audio-QA command, `--require-calibration --calibration-manifest ... --calibration-report ... --calibration-audio ...` performs the machine check **before any billable full-lecture transcription**. Rejecting an unqualified pair is a technical failure, not a manual gate. Omitting strict calibration retains the previous mode but explicitly reports `MODEL_CALIBRATION_NOT_PROVIDED`: that output must not claim Y/yay phonetic accuracy. Two cases are too small to establish population accuracy or other mathematical phoneme families. No original WAV, report, teaching video, or Moodle content is overwritten.
