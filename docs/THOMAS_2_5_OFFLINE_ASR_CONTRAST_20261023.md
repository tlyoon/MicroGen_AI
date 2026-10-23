# Thomas Calculus §2.5 — offline ASR pronunciation contrast, 23 October 2026

This is a **diagnostic-only** development finding, not a release approval. It extends the SHA-bound audio-trial comparison in draft PR #156. On HP only, the Python `vosk==0.3.45` recognizer and official Apache-2.0 English small model `vosk-model-small-en-us-0.15` were installed entirely under local AppData, with no paid provider requests, no Whisper, and no distribution of the model through this GitHub PR.

The downloaded model ZIP had SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`. Historical WAVs were resampled in temporary files to 16 kHz mono and transcribed using fully offline Vosk word timestamps.

## Observations (automated, not listening ground truth)

| Audio recording | ASR letter-word evidence |
|---|---|
| Slide 5 original | Three recognitions of "see" at approximately 9.09, 13.14, 18.00 s; no detected "circa" |
| Slide 5 C-dot trial | Three "see" recognitions at 8.57, 13.05, 18.48 s; improvement inconclusive |
| Slide 6 original | **Three "circa" recognitions** at 5.25, 10.47, 16.53 s, each model-reported confidence 1.0 |
| Slide 6 C-dot trial | "see", "sea", "see" recognized near 4.77, 10.02, 15.24 s, no "circa" recognition; model suggests improvement |
| Slide 10 original | One "why" recognition |
| Slide 10 Y-value trial | Two "why" recognitions |
| Slide 10 alternative PR35 trial | Two "why" recognitions, but source-video provenance is weaker than the Y-value QA receipt |

The source-bound `microgen_offline_pronunciation_contrast.py` validator verifies all seven WAV SHA values against PR #156's immutable review manifest, rejects altered, incomplete or chronologically invalid ASR observations, reports each word's diagnostic timestamp and confidence, and explicitly keeps every replacement unapproved. Review output on HP: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_asr_contrast_PR157_v2.json`. Original model-produced word evidence is at `2_5_offline_asr_probe_20261023.json`.

**Caveats:** Vosk ASR is fallible, especially for mathematical letter names and unusual notation. Model confidence 1.0 is not 100% certainty. Recognized "see" may be a real word rather than the variable c. Source verbal content, figure semantics, authenticated speaker identity, forced alignment with visual elements, and full academic QA are still NOT established. Neither observed ASR change nor matching SHA values authorize splicing the 24 kHz correction WAVs into an otherwise legacy 16 kHz/AAC audio mix. No publication or source changes were made.

The next essential integration task is a provider-neutral, genuinely acoustically grounded word-to-equation mapping with abstention on ambiguous math symbols, followed by an independent audio/listening and figure/math quality acceptance on a complete 17-slide candidate.
