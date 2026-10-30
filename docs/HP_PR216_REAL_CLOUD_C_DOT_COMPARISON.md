# PR #216 — Real Google Cloud TTS c-dot troubleshooting and offline word-screening

**30 October 2026, original MicroGen_AI, HP-only.** This is specifically authorized under the owner's merged PR #215 TTS contract: **Google Cloud TTS may be used for troubleshooting but is NOT the default for formal lecture WAVs**. We performed two tiny, one-call, isolated diagnostic experiments, not production media synthesis. No Gemini/Whisper requests, no protected source mutation, no publishing or fallback narrator substitution.

## Real A/B WAV observations

Actual configured Google Cloud TTS voice `en-US-Chirp-HD-F`, same short mathematical diagnostic utterance `Evaluate at c. Next, take the limit.`:

| Recorded utterance | Exact sent speech | Genuine WAV duration | WAV SHA-256 |
|---|---|---:|---|
| Control (deliberately unnormalized) | `Evaluate at c. Next, take the limit.` | **3.505333 s** | `df2ac759bb8abb4cec2493422f77cc152de80821c76d2359b910c2a1d7996bc3` |
| Current normalization | `Evaluate at see. Next, take the limit.` | **4.615333 s** | `5292dc9d803a9ee2cb0288b89f90b9285eb99669a6c1d08d5f69e1f055f31ba6` |

Both requests finished successfully, produced genuine mono 16-bit PCM WAV at 24 kHz, and were explicitly limited to **one Cloud request each** with no retries, using the authorized diagnostic pathway. The existing formal TTS provider setting was neither changed nor invoked. Provider identity `google_cloud_chirp3` is the *historical internal provider identifier* used by the package; the actual configured Cloud voice name is `en-US-Chirp-HD-F`, and this study makes **no claim** that the latter is a Chirp 3 voice.

Real independent offline **Vosk** small English model v0.15 (installed in an isolated HP AppData package directory, without modifying the production conda environment) screened the two genuine WAVs. This model's decoded word hypotheses are:

- Raw `c.`: **evaluate (1.0), at (1.0), circa (0.77152), next (1.0), take (1.0), the (1.0), limit (1.0)**.
- Normalized `see.`: **evaluate (1.0), at (1.0), sea (0.84609), next (1.0), take (1.0), the (1.0), limit (1.0)**.

The model recognized the same surrounding words. In this context its `sea` word hypothesis is consistent with the spoken name of letter C, and its `circa` hypothesis for the raw sample reproduces the original reported defect. This is **good supporting experimental evidence for the existing text normalization**, but a single Vosk model is NOT independent phoneme-level, human-listening or final academic QA proof. It is incorrect to claim a certain acoustic phoneme from this ASR alone.

## New code and durable integrity checks

- `microgen_cloud_tts_diagnostic.py` gains explicit `--literal-c-dot-comparison` for an uncorrected control sentence, restricted to a recognized mathematical c. cue with the existing normalization safety preflight. **No change to the formal TTS normalizer.** The default diagnostic request continues to normalize pronunciation correctly. All Cloud diagnostic safeguards (new isolated `*diagnostic*` directory; <=500 characters; --confirm-chargeable-diagnostic; one call; no retries; no formal WAV name or manifest; no publication) remain mandatory.
- `microgen_cloud_tts_pair_audit.py` is new, read-only and usable without Cloud: requires the *actual* control and corrected `diagnostic_receipt.json` and actual WAVs, verifies PCM characteristics and SHA, source utterance and normalized text hashes, same voice/provider/language, explicit uncorrected mode, request lengths and bounded calls. It can also validate an *optional independently generated offline Vosk report*, word hypotheses and their WAV SHA binding. Even when `circa` is flagged only in the raw sample and `sea` only in the corrected one, the audit **always records** `phonetic_identity_verified=false`, `same_speaker_acoustically_verified=false`, `production_lecture_generated=false` and `publication_allowed=false`.
- Dedicated no-cloud tests cover real PNG/WAV test evidence, uncorrected control being restricted to mathematical c. rather than names/historical dates, wrong speech length, duplicate paths, hash tamper, wrong voice, wrong source text, wrong normalization mode, ASR hash drift and attempted ungrounded ASR phonetic approval.
- The older first normalized Cloud receipt predates the new `synthesis_mode` field. This one historical receipt is accepted as normalized **only when the SHA of the exact normalized utterance also matches**, retaining source-bound conservatism; the *new raw control* must have the explicit `RAW_C_DOT_CONTROL_ONLY` label.

## HP evidence paths (external to original Drive repository)

- Normalized genuine diagnostic: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR216_diagnostic_cdot_normalized_001\diagnostic_cloud_tts_NOT_FORMAL.wav` plus `diagnostic_receipt.json`.
- Raw-control genuine diagnostic: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR216_diagnostic_cdot_literal_001\diagnostic_cloud_tts_NOT_FORMAL.wav` plus `diagnostic_receipt.json`.
- Genuine offline ASR evidence: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR216_REAL_PAIR_OFFLINE_ASR_SCREENING.json`.
- Independently validated, SHA-bound comparison: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261030_HP_PR216_CDOT_HASH_BOUND_PAIR_RECEIPT.json`.

All these items remain external to original G: textbook and lesson files. No Cloud requests are used in CI or test runs. Code is not a finished Serway 1.1 lecture; the formal provider default **remains unconfigured**.
