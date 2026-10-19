# PR #30: Localized audio QA review excerpts

The PR #25 acoustic comparison is strengthened for negative mathematical operators such as `not`, `never`, `greater` and `less`. This PR also adds checksum-verified review-excerpt extraction for all PR #27 risk-ledger entries. The tool validates the source narration and WAV SHA **before** creating an isolated new output folder; it will not overwrite an existing output path.

`python microgen_tts_audio_review.py PATH_TO_STAGED_WAVS PATH_TO_SCRIPT_TTS_JSON PATH_TO_RISK_REPORT NEW_QA_DIR`

Clip start times use **raw-character position as a rough estimate**, *not* phoneme or word alignment. Mathematical speech may differ in timing; reviewers should inspect the entire relevant slide when an excerpt misses the intended expression. PCM analysis reports silence and clipping but not phonetic quality. No original lecture audio is modified, no Whisper dependency is added, and clean ASR transcripts never grant publication approval.
