# HP-only source TTS provenance triage — 28 October 2026

This is the **original** MicroGen_AI repository. The PR branch is stacked on the exact PR #201 head `b7455c309f891bbea12870166d40a0416abde1fa`. All work is in a separate **HP** AppData checkout. No Dell-115, Yoga 6 or Zenbook; no source G: overwrite, paid TTS/API calls, Whisper or publication.

## Genuine original-textbook pilot

The production candidate is Thomas Calculus 13e Section 2.5, 23 slides, 23 authentic generated WAVs. Sources: isolated HP source mirror `20261026_HP_M1_SOURCE_ONLY/2.5`, exact 23-slide `script_tts.json`, `.microgen_tts_provenance.json`, authoritative checksum-bound risk register in `.microgen_tts_cache`. Output is separate: `20261028_HP_M1_SOURCE_TTS_PROVENANCE_TRIAGE/triage_receipt.json` and `risk_triage.csv`.

The new `microgen_source_tts_provenance_triage.py` validates SHA-256 of **each actual normalized TTS input**, the matching pinned provider and voice, all 23 WAV hashes, corresponding source TTS text, every risk location and every known risk class. It recomputes risks from source text and rejects source/provenance drift. The report is not acoustic speech recognition and makes no phonetic correctness claim.

**Observed verified result:** all 23 normalized TTS input hashes and 23 WAV/source hashes matched, with provider `google_cloud_chirp3` and fixed voice `en-US-Chirp-HD-F`. Among 69 source risk flags across 16 slides, **7** sentence-ending mathematical `c.` instances have a proven contextual `see.` conversion in the synthesized **text input** (NOT verified audible pronunciation). The other **62** standalone math-letter cases remain unresolved listening risks. No current audio was replaced or regenerated, and `publication_allowed=false`.

Risk count is NOT the count of confirmed errors; text normalization of the seven C-period cases is not an audible acceptance. A word ASR transcript may conceal a mispronunciation. True math/equation narration and figure-spoken synchronization also remain unverified.

## Regression and next steps

Ten new targeted tests cover exact normalization, unresolved symbol risks, non-mathematical `c. 1900`, immutable input, wrong WAV or text SHA, tampered risk positions, voice mismatch, reordered slides and forged approvals.

Next: run the full HP regression suite for the exact new branch, preserve the receipt, then independently establish real acoustic/semantic source evidence before removing any release blocks. Keep drafts unmerged and historical source unchanged while acceptance is incomplete.
