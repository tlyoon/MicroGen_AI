# PR #65 — Source PCM sample-exact independent clip verification

Separate from extraction: reopen every candidate WAV, verify its SHA-256, original WAV SHA-256, sample count/rate, ordered bounds and actual PCM frames against the pinned parent file's source sample range. Reject tampering, substituted audio, altered timestamps and any attempt to insert an unverified "WHY" / "YAY" label into an unlabelled candidate manifest. **Only structural integrity is verified**. No human approval gate, phoneme classification, paid model or source file modifications.
