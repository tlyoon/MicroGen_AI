# PR #218 — Pronunciation evidence inventory integrated into formal TTS pipeline

Original **tlyoon/MicroGen_AI**, HP-only. Follows merged PR217 generalized pronunciation grammar/closed-loop risk screening, and owner PR215 policy: **Google Cloud TTS may be used for bounded troubleshooting, but remains UNCONFIGURED as the default formal narration provider**. This PR made **zero** Cloud/Gemini/Whisper calls and changed no original textbook, lesson source, previous WAV or video.

## Code integration — what now happens automatically

After `text_to_speech_v25.py` has finished technical WAV checks, voice-identity/provenance manifest verification and the preexisting risk-register report, the program now calls `microgen_pronunciation_evidence_pipeline.build_post_tts_evidence()` and writes a **new immutable source/WAV-bound pronunciation evidence receipt** to `.microgen_tts_cache/pronunciation_evidence_<content SHA>.json`. This call is local/offline, uses the existing normalized narration and SHA-256 of each `slideN.wav` plus the TTS provider manifest and available `script_tts.json`, and never invokes a speech provider or requires an ASR model. It is integrated into the **normal successful TTS stage**, not a manually triggered separate step. Repeated resume with identical sources returns the same report; changed WAVs get a new report without destroying prior evidence. Missing/altered WAVs, incorrect slide order and mismatched script evidence fail closed instead of making false QA claims.

The report is **NOT a publication approval or acoustic QA pass**: no recordings are marked phoneme-authenticated. Its initial mode uses only source narration, source-pronunciation risks and WAV identities; when a separately generated offline recognizer report becomes available, the same module can be rerun with `--offline-asr-dir` to add per-slide discrepancies. This distinction avoids systematically stalling valid lecture generation on ASR ambiguity and avoids paid provider traffic at each successful TTS stage.

The new companion CLI works with a previously generated source-grounded stage:
```powershell
python microgen_pronunciation_evidence_pipeline.py `
  --stage "C:\path\to\existing\lesson\stage" `
  --offline-asr-dir "C:\path\to\independent\slideXX_asr" `
  --new-external-directory "C:\new\local\pronunciation_evidence"
```
The ASR directory is optional. The authoritative source `script_tts.json`, existing WAVs and their SHA-bound Vosk slideXX reports are read only. Every candidate includes source/recognizer word hypotheses, source slide identity, and original WAV hash. Candidate categories: `POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED`, `REPEATED_GENERAL_WORD_DIFFERENCE_ADVISORY`, `ISOLATED_UNVERIFIED_WORD_DIFFERENCE`, `POSSIBLE_HOMOPHONE_OR_ASR_VARIANT`, and `ALIGNMENT_INSERTION_OR_OMISSION_UNVERIFIED`. The catalog's common homophone/ASR-variant pairs are **screening heuristics, not verified pronunciation ground truth**, and never authorize an automatic technical word substitution.

## Genuine original HP evidence

Audited the **23 actual Thomas Calculus Section 2.5 lecture WAVs**, unchanged original narration sidecar, and 23 previously captured SHA-bound Vosk slide reports from the original HP generation campaign:
- Stage: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY\2.5`
- Independent offline ASR: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_FRESH_ASR_23`
- New independent evidence: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR218_REAL_THOMAS_TECHNICAL_EVIDENCE\pronunciation_evidence_90071418a596148875d3.json`

All 23 WAV SHA-256 checks and recognition-to-WAV identities passed. Across 23 slides, the system found **69 source math pronunciation-risk entries**, 91 different ASR text-difference patterns, including **11 potentially technical-term discrepancies**, 10 likely homophone/ASR variants and 14 alignment insertions/deletions. This is *not* a count of 91 mispronunciations: for example, Vosk returned `cosine` → `coast sign` or `kosane`, `polynomial` → `apollo no meal`, `theorem` → `serum eight`, `numerator` → `numerate or`. These phrases alone are **insufficient to diagnose actual incorrect pronunciation**. Technical terms stay as ranked **unverified candidates** for future targeted acoustic comparison, not automatically replaced words. The receipt has `publication_allowed=false`, `phonetic_identity_verified=false` and `provider_calls=0`.

## Tests and remaining work

Add tests for actual PCM WAV/test-source composition, manifest and text hash binding, source mismatch and corrupt/missing WAV refusal, SHA-bound ASR evidence and forged 'verified' claim rejection, idempotent immutable save, protection against overwriting source Drive, recognition variant classification and target scientific candidate ranking. Existing TTS normalization and fixed pronunciation rules still receive full regression coverage.

This solves the **automatic post-TTS evidence capture and usable error-discovery shortlist**. It does NOT automatically fix every previously unknown mispronunciation, nor does it generate the as-yet-unfinished full Serway §1.1 narrated MP4. The owner has not approved a formal default TTS provider or new billed Gemini generation campaign. Future PRs should prioritize targeted independent phonetic trials of the 11 Thomas technical-word candidates only when supported by additional acoustic evidence, and separately close the full Serway source-to-video provider dependency.
