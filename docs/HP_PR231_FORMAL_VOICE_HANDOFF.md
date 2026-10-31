# PR231 — Source-bound formal narration synthesis handoff

This is a no-network and no-TTS **production input** workflow; it is not a production
voice, synthesis result, publication decision or manual approval requirement.

Run only in the authorized original MicroGen_AI HP checkout, with immutable
**external HP** reports from PR226, PR229, PR230 and PR228:

```powershell
python microgen_formal_voice_handoff.py `
  --narration-qa "<PR226 verified_narration.json>" `
  --critical-claims "<PR229 original physics audit.json>" `
  --figure-panels "<PR230 original image panel audit.json>" `
  --diagnostic-dir "<PR228 immutable diagnostic AV directory>" `
  --new-output "<new external HP formal-tts-input-bundle.json>"
```

The tool rejects source hashes that do not agree across the original source,
eight speech texts, rendered slide, critical facts, both image panels and
diagnostic video receipt. It refuses attempts to promote diagnostic audio to
formal voice, tampered video bytes, missing slide-frame evidence and excessive
duration drift.

**Formal voice authority is separate from legacy configuration.** The historical
repository voice identifier `en-US-Chirp-HD-F` is recorded for continuity but
neither it nor the diagnostic `Microsoft Zira Desktop` represents current
authorization to make billed provider calls or production audio. Diagnostic
Google Cloud remains permitted only for troubleshooting within owner policy.
Both the provider and approved formal voice fields remain `null`.

The output lists eight SHA-pinned plain-ASCII narration inputs, outstanding
production constraints, and explicit no-production/no-publication flags.
The user has required autonomous QA; human reviews are not hard prerequisites
in the existing technical release policy. Academic and pronunciation assertions
must never exceed the scope of the independent technical evidence.

Real HP output path:
`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR231_PRODUCTION_TTS_HANDOFF.json`.

Next: verify an authorized, compatible, no-cost formal voice within the
existing contract (or a separate explicit change in paid-provider policy),
perform original-audio-bound formal synthesis, and independently QA generated
WAVs and synchronized MP4. Never substitute a diagnostic voice automatically.
