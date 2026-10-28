# PR #62 — Real before/after WAV diagnostics with immutable external evidence

Run without any paid provider, additional libraries, or human gate:

python microgen_tts_pair_diagnostics.py BEFORE.wav AFTER.wav NEW_EXTERNAL.json --before-sha256 VERIFIED_BAD_SHA --after-sha256 VERIFIED_GOOD_SHA

The command validates both SHA-256 references before and after, uses short-time WAV signal/texture metrics, checks confidence of bounded alignment, and emits any localized acoustic divergence only where alignment is actually defensible. Report creation uses exclusive-write outside both source directories. This is only evidence of measurable AUDIO DIFFERENCES, not a transcription or phonetic/academic QA pass. A weak correlation leads to explicit ABSTAIN; a successful command means report generation, NOT lecture publishability.

Observed actual Thomas Calculus 2.5 Slide 10 defective and corrected WAVs have durations 33.145333/32.905333 seconds and a best attempted envelope correlation of only 0.290544. The correct result is LOW_SIMILARITY_UNALIGNABLE and zero claimed word hotspots. Do not claim the cause of the different synthesis signals is the y-value pronunciation until an independently calibrated phoneme-sensitive method works. Earlier Gemini transcription and contrastive model pairs remain unqualified.
