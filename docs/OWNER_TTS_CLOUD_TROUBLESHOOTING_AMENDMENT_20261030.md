# Owner amendment — Google Cloud TTS permitted for troubleshooting; not default formal TTS

**Effective:** 30 October 2026 (Asia/Kuala_Lumpur)

**Project:** original `tlyoon/MicroGen_AI`, NOT `MicroGen_AI_Web`.
**Priority:** This specific owner amendment supersedes earlier blanket prohibitions on Google Cloud TTS troubleshooting and the former *implicit* Google Cloud formal TTS default. All remaining project safety, academic, source-fidelity and release rules remain in force.

## Authorized provider policy

1. **Google Cloud Text-to-Speech is authorized for troubleshooting.** Diagnostic pronunciation tests, voice checks, provider failures, request/response testing and related debugging may use the existing Google Cloud TTS service, even when a legitimate API charge may result. No separate per-test owner approval is required within this narrow permission.
2. **Google Cloud is *not* the default provider for formal lecture TTS.** Formal source-to-WAV and publication campaigns must not select it merely because the service credentials or earlier WAVs exist. The project has not yet approved a substitute default production voice/provider. The formal default is therefore **unconfigured / fail closed** until an owner-approved production provider is selected. This is a deliberate pending decision, not a claim that an equivalent alternative exists.
3. The existing `en-US-Chirp-HD-F` voice is retained as **historical configured voice identity and source/provenance reference**, but the same voice label is **not** automatic authority to issue formal cloud synthesis. To explicitly choose Cloud for an exceptional formal run, an authorized operator must separately set `MICROGEN_FORMAL_TTS_PROVIDER=google_cloud`; the existing batch flag `--authorize-provider-usage` and the applicable cost authorization still apply. This selection is an opt-in, never the default and not provided by this amendment.
4. Diagnostic output is **not formal lecture content**. It must be produced in an isolated new local folder, never `slideN.wav`, without production script/voice manifest or media publication. Do not promote a diagnostic WAV into formal lecture media merely because it is technically valid or uses the same voice name. Mathematical/phonetic quality and independent narration-source QA remain required for production.
5. **Bounded cost safeguard:** The diagnostic helper issues at most **one TTS request per invocation**, for up to **500 normalized characters**, with **no automatic retries**, requiring a clearly diagnostic output directory and the explicit operational CLI flag `--confirm-chargeable-diagnostic`. Repeat bounded trials only when useful for troubleshooting. The user has already authorized this class of troubleshooting; the CLI flag is a safeguard against accidental invocation, not a renewed permission request. Record the input hash, provider voice, WAV hash/format and charged-test flag in an immutable diagnostic receipt.
6. This amendment **does not authorize** billed Gemini API work, paid Whisper/transcription, general unlimited cloud requests, unbounded formal lecture-generation costs, cross-device development, protected source edits or automatic YouTube/Moodle publication. Original MicroGen_AI development/testing remains **HP-only**.

## Implemented code contract

- `microgen_tts_provider_policy.py`: one authoritative formal-provider default `unconfigured`, fail-closed policy, and bounded diagnostic allowance.
- `text_to_speech_v25.py`: checks explicitly selected formal provider **before** credentials, cache, WAV creation or requests; direct `synthesize()` is likewise guarded after pronunciation preflight. Existing formal Cloud generation remains an explicit opt-in; no voice is silently substituted. Google Cloud synthesis now supports the diagnostic single-attempt mode independently of formal four-attempt retry behavior.
- `microgen_cloud_tts_diagnostic.py`: the authorized standalone small Cloud TTS troubleshooting path. It cannot write into an existing folder, protected source Drive or a production lecture destination, and always creates `diagnostic_cloud_tts_NOT_FORMAL.wav` and `diagnostic_receipt.json`. A failure removes only the new directory created by that invocation.
- Historical source/WAV provenance and existing saved teaching videos are **unchanged**. Existing regression tests that require the historical formal Cloud provider explicitly declare it instead of relying on an implicit default.

### Operational example — bounded Cloud troubleshooting only

```powershell
python microgen_cloud_tts_diagnostic.py `
  --text "Evaluate at c. Next, take the limit." `
  --new-diagnostic-directory "$env:LOCALAPPDATA\MicroGen_AI_Diagnostics\diagnostic_c_dot_001" `
  --confirm-chargeable-diagnostic
```

The example **may make a chargeable API request**. It is not a formal lecture run; it produces no `slideN.wav` or publishing approval.

Formal TTS remains blocked by default even if `MICROVID_TTS_VOICE=en-US-Chirp-HD-F` and Google credentials are present. A full batch requires its existing provider-authorization flag, and formal Cloud selection additionally requires the separate explicit provider setting.

### Completion status

This is a contract and execution-safety change, **not** a claim that Serway 1.1 final narration/production WAVs exist. The validated PDF extraction, source-figure mapping and eight-slide draft remain the latest real Serway 1.1 outputs until a formal production provider is chosen. No paid Cloud diagnostic is required merely to validate this contract amendment; all new regression tests use a fake local WAV and mocks.
