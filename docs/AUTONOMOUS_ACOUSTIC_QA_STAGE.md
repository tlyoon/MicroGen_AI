# Autonomous independent acoustic QA — PR #274

**Original API-based MicroGen_AI on HP only.** No local models, no mandatory
human approval, and no original source/MP4 publication.

## Position in the production pipeline

```text
source/figures → slides → narration → scientific QA
→ Gemini TTS → autonomous independent acoustic QA → slide slicing → video
```

The new `acoustic_qa` stage is part of the production
`microgen_batch.py` checkpoint contract. It runs before any media assembly
and requires complete SHA-bound voice/WAV metadata and PCM-integrity
screening. Gemini model families `gemini-3.5-flash` and `gemini-3.8-flash`
are queried independently, with audio only—**without supplying expected
transcripts to either recognizer**. Both ASR hypotheses are checked against
the normalised source utterance and one another using the existing
`microgen_tts_acoustic_qa` and `microgen_tts_evidence` modules.

An all-slide pass is a **limited acoustic screen**, not phonetic proof.
Technically passed receipts retain
`human_approval_required=false`, `pronunciation_perfection_certified=false`,
`publication_allowed=false`. Historical ASR status strings containing the
word "LISTENING_REQUIRED" remain compatibility metadata and are *not* a
development human gate. Wrongly pronounced scientific symbols, units,
numbers or sensitive mathematical terms still block if detected.

If one/two independently corroborated speech slips are detected, at most
**one targeted same-source-text, same-Gemini-engine, same-Kore-voice** WAV
regeneration is attempted for each affected slide. Candidate WAVs are
first created in private scratch, PCM checked and transcribed by both
recognizers. Only after this may source-bound WAV records and the original
batch TTS manifest be updated together with rollback on any validation error.
No source PDF, slides, script or existing video is rewritten. Provider
changes, unclear speech, transcript-model disagreements, uncertain
source-pronunciation risks, more than two defective slides, and repeated
failures block the stage without unbounded model/TTS loops.

The final `.microgen_autonomous_acoustic_qa.json` includes the validated
**full independent recognition report** and SHA-bound TTS provenance.
Production resume checks include the stage implementation hash, each WAV
hash, script sidecar and immutable transcript receipt. A distinct
`.microgen_acoustic_blocked_<sha>.json` records bounded technical failures,
never an approval. No human intervention is needed to proceed on success.

The existing strict `microgen_tts_release_audit` can independently verify
the embedded `independent_report` through
`verify_acoustic_evidence`. A release decision additionally requires
source/scientific, PCM, figure and A/V evidence through the unified gate.

## Limits

ASR cannot guarantee every English/math phoneme is correctly pronounced.
An independent model can miss the same error as the other model. Textbook
scientific correctness and publication/redistribution rights are separate
matters; the stage does not claim those attributes.

This QA stage is designed for a *single bounded attempt per invocation*,
not a perpetual per-PDF correction loop. Gemini outages produce a technical
fail-closed result. Gaussian-level or phonetic scoring is not invented.
