# PR #217 — Generalized TTS pronunciation QA and selective repair

Original `tlyoon/MicroGen_AI`, HP-only, governed by the owner-amended Cloud TTS troubleshooting policy from PR #215. This is an actual **source-bound, testable closed-loop foundation**. It does not claim that every mispronounced word can already be discovered from speech recognition or that any lecture is publication-certified.

## What changed

- Added `microgen_pronunciation_closed_loop.py`, an offline first-pass pronunciation normalizer/risk+WAV/ASR auditor, immutable QA planner and **selective, bounded diagnostic regeneration** function. Given `script_tts.json` and actual slide WAVs plus hash-bound Vosk per-slide observations, the CLI automatically: (1) compares source input to carefully rewritten **TTS-only** speech; (2) identifies source-specific mathematical risks, safe speech expansions and unresolved constructs; (3) computes a token-level ASR mismatch inventory; (4) finds known high-confidence mispronunciations *aligned to the expected mathematical term* (not a stray 'circa' elsewhere); (5) generates an independent plan for only affected slides; (6) can, when explicitly invoked, generate **at most two** separate, max-500-character Google Cloud diagnostic WAVs via the existing retry-disabled diagnostic helper. It never edits the original source/narration, production `slideN.wav`, TTS cache, voice manifest or final video. New WAVs always require follow-up audio QA before any approval.
- A versioned, safety-checked glossary `docs/tts_conservative_math_expansions_v2.json` adds **more than the existing c./y cases**: tightly scoped `sin(x)` → 'sine of ex', `cos(y)` → 'cosine of why', `tan(t)`, `ln(x)` → 'natural logarithm of ex', `f(x)` → 'eff of ex', `g(y)`, `h(t)`, and single-digit coordinate subscripts `x_1` → 'ex subscript one' etc. Rules are restricted to exact single-letter elementary argument/index shapes and validated against negative examples; `sin(x+y)`, `x_12`, `a_n`, `arcsin(x)` and other ambiguous mathematical expressions remain unchanged and unsafe/review-required. Source equations and textbook wording are **never rewritten**.
- `text_to_speech_v25.normalize_scientific_speech` applies these deterministic, reviewed text-only expansions *before* existing symbols/unit/c./y normalizations. The existing math pronunciation preflight and voice provider/provenance gates remain active. Unrecognized terms cannot trigger speculative lexical substitution.
- The existing `microgen_tts_risk_register.py` now recognizes specifically approved elementary function and single-digit subscript expansions as automated TTS input normalization, while still marking other unreviewed abbreviations/subscripts requiring review. Risk inventory is not final listening approval.
- A separate `run_isolated_diagnostic_repairs` handler can selectively regenerate only SHA-grounded high-confidence known problems, with no automatic SDK/API calls in import or normal audit. A complete lecture with more than two candidates is not silently billed: the handler refuses the overly broad request and requires an explicitly bounded diagnostic selection. An unrelated Vosk mismatch by itself does not authorize charges or automatic rewriting.

## Actual real HP evidence, not mocked

1. **23 existing genuine Thomas Calculus Section 2.5 WAVs** were independently audited against their unchanged source `script_tts.json` and 23 existing offline Vosk observations. Each slide WAV and recognition result was SHA-256 matched. Source: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY\2.5`. ASR reference: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_FRESH_ASR_23`. Immutable aggregate QA receipt: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR217_THOMAS25_23_SLIDE_QA_PLAN.json`. This run detected many source mathematical risks and word hypotheses but selected **0 high-confidence chargeable regeneration candidates**. It did not approve the other 23 recordings or treat a generic recognizer mismatch as proven bad speech.
2. A **new real Google Cloud TTS** single-call short diagnostic of the sentence `Let f(x) equal sin(x), and let x_1 be the initial position.` was synthesized under the already authorized troubleshooting contract with configured `en-US-Chirp-HD-F`. WAV: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR217_diagnostic_multiple_math_forms_001\diagnostic_cloud_tts_NOT_FORMAL.wav`. Length **7.045333 seconds**, mono 24 kHz, formal voice provider still `unconfigured`. No retries. The normalizer sends the context-corrected speech instead of raw notation. Isolated SHA-bound diagnostic receipt alongside WAV. Offline Vosk v0.15 screening: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR217_MATH_FORM_CLOUD_OFFLINE_ASR.json`. Vosk recognized `f/of/acts`, `sign/of/acts` and `x/subscript/one`; 'sign' for 'sine' can be a homophone, and 'acts' for 'ex' may be recognizer uncertainty. We do **not** certify phonemes or blindly initiate retry based on these ambiguous outputs.

## Usage

Offline entire original lecture, no network or Cloud requests:

```powershell
python microgen_pronunciation_closed_loop.py `
  --script-tts "PATH\TO\script_tts.json" `
  --wav-folder "PATH\TO\ORIGINAL_SLIDE_WAVS" `
  --offline-asr-dir "PATH\TO\PER_SLIDE_SHA_BOUND_VOSK_JSON" `
  --new-plan "NEW_LOCAL_QA_REPORT.json"
```

Optional **explicit, chargeable bounded diagnostic regeneration** of up to two verified known-problem slides:

```powershell
python microgen_pronunciation_closed_loop.py `
  --script-tts "PATH\TO\script_tts.json" `
  --wav-folder "PATH\TO\ORIGINAL_SLIDE_WAVS" `
  --offline-asr-dir "PATH\TO\PER_SLIDE_SHA_BOUND_VOSK_JSON" `
  --new-plan "ANOTHER_NEW_LOCAL_QA_REPORT.json" `
  --execute-bounded-diagnostics "NEW_LOCAL_diagnostic_REPAIR_DIRECTORY"
```

The optional diagnostic regeneration **never overwrites formal WAVs** and is only eligible for known high-confidence source-grounded faults such as c → circa or y → yay. If no such errors are found it incurs **zero requests**, and if too many are found it refuses an unbounded campaign. A separate independent recognition pass on any newly regenerated WAV is still required.

## Unresolved honest limitation

General-purpose ASR is not a phonetic oracle. Wrongly pronounced legitimate words can still be transcribed as the expected spelling, and correct technical speech may be transcribed incorrectly. This change **does not guarantee detection and correction of every unknown mispronunciation**. Future work should add a controlled scientific pronunciation knowledge base, more independently verified examples, targeted acoustic classifiers and adaptive candidate selection. A risk screen cannot automatically override mathematical correctness, source grounding, or the separate owner publication/release contract.

All work confined to HP; no protected textbook edits; no formal Google Cloud provider selection; no lecture publication.

## Controlled long-term technical-word glossary expansion

The v2 JSON grammar is deliberately data-driven. Additional, confirmed mispronounced scientific words may be added with `replacement_kind=technical_term`, a *narrow* context/boundary-aware `regex`, explicit English `spoken_form`, one `reviewed_evidence_sha256` that links to the separately preserved acoustic evidence, plus **positive and negative examples**. Schema validation refuses missing acoustic evidence hashes, invalid spoken forms, duplicate rule IDs, overbroad matches detected by negative examples and unknown template operations. A generic technical-word pattern can be added without a change to the Python normalizer, but adding a hash string is **not** proof of correct phonemes; real independent audio checks and human/domain review of the particular term remain essential. A synthetic-only test entry demonstrates the extension mechanism; no unreviewed real technical-word override is deployed by this PR.

The new risk register marks only the exact reviewed elementary `f(x)`, `sin(x)`, `ln(x)` and single-digit `x_1`-style patterns as having an automatic **speech-input** interpretation. Source wording, mathematics and unreviewed forms (`f(x+y)`, `x_12`, symbolic subscripts, bare `sin x`) remain protected. Existing isolated repair logic may now propose these safe text expansions, but still requires a separate acoustic gate and never promotes its output as published audio without acceptance.

The 23-slide real Thomas §2.5 run found 69 potential source mathematical pronunciation-risk entries, 6 slide texts where normalization changed the spoken request, and 23 slides with at least one offline ASR word difference. These are **risk/screening observations**, not 69 confirmed mistakes; none met the narrow high-confidence auto-regeneration threshold, so **zero cloud repair requests** were made for those original WAVs. This prevents overly stringent QA from regenerating or blocking every plausible recognizer variation.
