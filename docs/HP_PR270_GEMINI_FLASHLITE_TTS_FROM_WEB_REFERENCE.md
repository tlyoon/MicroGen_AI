# PR270 — API-based MicroGen_AI uses the same Flash-Lite TTS choice as MicroGen_AI_Web

**Owner request:** 4 November 2026, explicitly port the **TTS engine/default and fallback hierarchy** from the separate Selenium repository in Google Drive to the **original API-based MicroGen_AI**. The Web reference was read ONLY through connected Google Drive and NEVER modified or executed. Code/tests/SDK installation happened on the authorized **HP desktop only**, no Dell/Yoga6/Zenbook, no local language model.

## Authoritative source reference (read-only)

The owner-provided Google Drive folder is
`https://drive.google.com/drive/folders/1y3OmXv_OE9Z4uFjzCcDRzhVbsdjDnCqp`.

Its relevant files were `selenium_pipeline/tts.py` and `selenium_pipeline/README.md` within folder `1FWTw885FLo_cuqTZPUfSPTzdQDMjAdej`.

**Executable source** `selenium_pipeline/tts.py` main defaults:
- `--provider gemini`
- `--model gemini-3.8-flash-lite-tts`
- `--voice Kore`
- on failures `gemini-3.8-flash-tts` then Google Cloud `chirp3-hd` as fallback.
- `_fallback_specs()` maps Kore to `en-US-Chirp3-HD-Kore`. The Web README also mentions Cloud `Aoede`, which conflicts with this executable mapping; implementation follows **the executable code**, not the conflicting line in README.
- Original speech style: calm, natural university physics narration, precise scientific and mathematical language.
- Gemini API `generate_content` uses `speech_metadata.style`, `response_modalities=['AUDIO']` and `speech_config.voice_config.voice`; response is a complete WAV (not raw PCM).

Google now documents the two exact model IDs, the unified voice schema and the complete WAV response:
`https://ai.google.dev/gemini-api/docs/speech-generation`
and Google Gen AI SDK **>=2.33.0** is required in its current examples.
Source code and owner instructions take priority over unsupported pricing guesses.

## What changed — ONLY in original MicroGen_AI

1. `microgen_tts_provider_policy.py`: The *absent* formal selector now resolves to `gemini`; explicitly configured `unconfigured`/off still refuses TTS; `google_cloud` retains its separate explicit legacy route. The longstanding Oct 30 Cloud diagnostic-only permission is **not** a mandate to use Cloud for formal synthesis. Its historical voice is still `en-US-Chirp-HD-F` for provenance only.
2. `microgen_flash_tts.py`: API-native Gemini 3.8 Flash-Lite with default `Kore` and the Web speech style/schema, existing `gemini_keys.py` key-pool failover, subprocess watchdog, bounded retry, sentence-aware chunking after timeout, PCM16 WAV validation, atomic private batch, SHA-bound text/audio receipt and strict single-engine/voice fallback. First fallback is Gemini Flash; last optional fallback is Chirp 3 HD with matching `en-US-Chirp3-HD-Kore` voice. A failed fallback never produces partial approved WAVs.
3. `text_to_speech_v25.py`: Existing API pipeline `script_tts.json` / `script.txt` entry point now runs the Flash-Lite full-lesson batch by default with the existing math pronunciations, lexicon preflight, voice-bound WAV SHA provenance, cache manifest, offline QA evidence, and rollback. The explicit Cloud historical path remains available for old/diagnostic workflows but is NOT default. **Only TTS changed**; no Selenium migration and no change in the figure/slides/narration authoring models.
4. `microgen_tts_provenance.py`: The two Gemini models gain pinned configured-voice SHA provenance while SAPI/unverified voices remain rejected; no older Cloud record is silently reclassified as Gemini.
5. `microgen_flash_chapter_tts.py`: The actual PR267/268 six-section original Chapter 1 handoff can be preflighted without payment, then (only on explicit run request) synthesize 57 source-aligned texts through **one common batch engine**, populate per-section WAVs, and invoke existing PR269 capture-manifest integrity audit. It writes a private PR268-ready capture plan with rebased atomic paths. User can then run PR268 to produce six private videos.
6. `requirements.txt` raises `google-genai` to >=2.33,<3. Authorized HP environment upgraded to 2.34.0; no local language model was installed.

## Fallback safety and fidelity

**Default:** `Gemini 3.8 Flash-Lite` -> on failure try `Gemini 3.8 Flash`. This matches Web model/voice and priority. The Web module optionally tries per-slide mixed-model fallbacks with an external voice-similarity gate, then redoes whole batch if that fails. For original MicroGen_AI the safer **whole-batch fallback** is the sole production path; this preserves the existing original repo's stricter single-provider completion contract and avoids voice mixing. Both engines produce complete WAVs; they are not speech content/phonetic approval.

**Google Cloud:** Never primary without explicit `MICROGEN_FORMAL_TTS_PROVIDER=google_cloud` (legacy). Under Flash-Lite, **Chirp 3 HD only runs if** `MICROGEN_TTS_ENABLE_CLOUD_FALLBACK=1` and `MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS` is a positive permitted per-batch cumulative character ceiling; every Cloud attempt counts against the ceiling, including failures. The Cloud voice uses the same named `Kore` as the Gemini default; **no default or automatic paid Cloud fallback** without the operator opt-in. The existing authorized bounded troubleshooting API is a separate CLI and remains unchanged.

**Gemini API charges** also require account/quota and are **not a browser subscription entitlement**. The new chapter command's default is dry-run; an explicit `--authorize-paid-gemini-tts` flag is required before real chapter syntheses. No live paid TTS, Geminis, Cloud, or speech models called during PR270 development/tests.

## Real owner-private Serway Chapter 1 integration

Preflight command run on HP with exit code 0:
```powershell
$root=Join-Path $env:LOCALAPPDATA 'MicroGen_AI_Checkpoints'
$bundle=Join-Path $root '20261103_HP_PR267_SERWAY1_SIX_SECTION_REAUDITED_VOICE_PRIVATE'
$plan=Join-Path $root '20261103_HP_PR268_SERWAY_CHAPTER1_SOURCE_BOUND_AUDIO_PLAN_V2_PRIVATE.json'
python microgen_flash_chapter_tts.py --chapter-bundle $bundle --blank-source-plan $plan
```
Result: 6 sections / 57 exact SHA-bound narration requests / 35,714 input characters / default Gemini model `gemini-3.8-flash-lite-tts`, voice `Kore`, zero paid calls, publication false.

Only AFTER the owner explicitly authorizes billed Gemini TTS production and appropriate cost:
```powershell
python microgen_flash_chapter_tts.py --chapter-bundle $bundle --blank-source-plan $plan --new-private-output $fresh_output --authorize-paid-gemini-tts
```
This produces one private chapter WAV collection and PR269 capture verification. Its receipt continues to set `publication_allowed=false`. If the owner separately authorizes cloud fallback, operator sets the cumulative Cloud character budget and adds `--allow-cloud-fallback`. **Do not upload protected textbook/narration assets or WAVs to public GitHub or Google Drive.**

Feed `$fresh_output/verified_capture/capture_plan_ready.json` into `microgen_private_chapter_audio_video.py` using its `--render-private-videos` option for six source-PDF-frame verified PRIVATE preview MP4s, then independently review actual pronunciations, academic claims and copyright/release rights. No publication without a separate decision.

## Acceptance gates

Synthetic focused tests exercise exact provider/model/voice names, Google Gen AI request structure, complete WAV response, Gemini key failover hooks, PCM validation, timeout chunk merge, all-or-nothing whole-batch fallback, Cloud last-only with cumulative budget, explicit historic Cloud route, old provider-policy tests, cache/source provenance and legacy entry point, and original PR267 -> PR269 -> PR268 two-section full FFmpeg MP4 QA without paid API use. Require full HP root pytest exit 0 and **all four** GitHub Ubuntu/Windows Python 3.11/3.12 jobs on exact PR270 head before squash merge.
