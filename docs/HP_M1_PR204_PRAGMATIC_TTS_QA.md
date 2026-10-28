# HP-only pragmatic TTS QA contract — 28 October 2026

Original **MicroGen_AI**, not MicroGen_AI_Web. Owner-approved change: avoid repeated or stalled synthesis when a TTS WAV is usable and minor or unverified notation issues are the only remaining concerns. HP is the sole authorized local device. Keep provider/voice and recorded audio provenance; no unapproved rewriting of source textbook PDFs or video assets.

## Three distinct decisions

1. **Technical WAV preflight (mandatory):** ordered complete narration, exact SHA-bound original/normalized TTS inputs, provider/voice and actual WAV bytes, valid mono 16-bit PCM, non-silent audio, no severe clipping, reviewed source math notation/lexicon rules. Any definite failure here means `REPAIR_CRITICAL_AUDIO_DEFECT`. No waiver.
2. **Media-generation progression (default, nonpublishing):** minor wording/orthographic differences, math-letter *risk flags without specific negative evidence*, low signal level advisories, and unavailable or disagreeing-unimportant ASR are **not** automatic blockers or reasons to pay for a new TTS clip. Continue with `CONTINUE_WITH_ADVISORIES` while preserving WAV and receipt. A concrete `c`→“circa” or mathematical `y`→“yay” red flag, independently reported substantive equation-term mismatch, demonstrably unsafe spoken input, unreadable WAV or bad voice/source hash remains a blocker. Do not blindly retry on Gemini/ASR outages.
3. **Final semantic, narration-highlight and publication acceptance (separate):** progression is NOT verified pronunciation or approval. The strict independent-acoustic receipt and final release checks are **unchanged**. Academic figure correctness, spoken math meaning and true equation/figure synchronization remain outstanding. No automatic YouTube/Moodle publishing, G: overwrite, or false certification.

This deliberately permits useful pipeline work while a secondary recognizer is unavailable, and reserves acoustic re-synthesis for credible, concrete error evidence. Source risk flags are advisory hypotheses, not proof of wrong audio. A transcript that agrees with source text is also not a phonetic oracle.

## Changes

- `microgen_pragmatic_audio_qa.py` provides an optional read-only *real WAV* check, accepts a SHA-bound existing Vosk observation folder, and emits an immutable/new-file JSON report with publication explicitly prohibited.
- `microgen_tts_release_audit.audit_stage` now returns a separate `audio_generation_progression`, preserving the legacy final `checks` and release `technical_blockers` without weakening release proof.
- `microgen_tts_quality_campaign` writes `TTS_MEDIA_GENERATION_PROGRESSION.json` alongside its ordinary strict release report.
- Changed OpenCV figure tests from module-level `pytest.importorskip` to `unittest.skipUnless` so the existing GitHub Actions `unittest discover` runner can skip optional OpenCV cleanly. PR #203 failed CI solely because import-time pytest skip raised an exception in unittest discovery; full prior HP regression was green. The fix keeps CI without installing costly GPU/vision dependencies.

## Genuine HP pilot

Thomas Calculus 13e §2.5: 23 real WAVs and source narration, original TTS provenance, immutable 69-risk ledger, optional actual 23-slide offline Vosk evidence. Read-only result: `CONTINUE_WITH_ADVISORIES`, `can_continue_media_generation=true`, `publication_allowed=false`; 69 notation risk flags do NOT mean 69 confirmed audio defects. 7 C-period instances already had source input normalized to “see.”, but acoustic accuracy remains unverified. The 15 source-mapped figure pixels had no low-match flags in PR #203; math semantics and highlight synchronization are still not certified.

All acceptance reports, source audio and prior drafts remain preserved. If the next stage requires paid TTS, do not issue provider calls for minor advisories; only regenerate affected clips after a critical error is demonstrated and a reviewed correction is available.
