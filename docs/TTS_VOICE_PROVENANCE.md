# TTS voice provenance and verified reuse (PR #24)

Built on the pronunciation preflight in PR #23 and the mathematical `c.`
correction in PR #22. The normal TTS pipeline records the provider,
requested cloud voice, language, speaking rate, location, normalized
**spoken input SHA-256**, audio SHA-256 and measured PCM properties for each
slide. No credentials, API keys, or plaintext narrated passages are
included in the verification receipt.

## Completion and cache

Every slide's cache metadata is schema-verified before reuse, including
input digest, voice/rate/provider and actual WAV sample format and SHA-256.
Legacy unverified cache entries are not reused without regeneration.
The cache key now uses `microgen-tts-v3-provenance` to invalidate previously
unverified v2 records safely. Any existing WAV is backed up before replacement.

When all slides verify under a single pinned Google Cloud voice, the
system atomically writes `.microgen_tts_provenance.json`. Downstream QA
may independently check it with:

```python
from pathlib import Path
from microgen_tts_provenance import verify_manifest
from text_to_speech_v25 import normalize_scientific_speech
# Provide the slide tts_text values in canonical slide order.
verified = verify_manifest(Path("lesson"), [normalize_scientific_speech(x) for x in slide_texts])
```

A missing/malformed/old receipt, corrupt WAV, changed input, changed
configured voice or sample format, or mixed provider fails verification.
The mixed-provider guard is evaluated **before** replacing the affected
slide WAV, so a provider-switch attempt does not overwrite that file.
A failed run cannot emit a new verified completion manifest.

## Fallback boundary

This patch does not select a different TTS provider or change retry
policy. The existing opt-in Windows SAPI fallback may still synthesize,
but SAPI currently uses a machine-selected voice that the code cannot
pin or attest; therefore it **cannot** be claimed as verified single
voice under this receipt schema. It must be re-synthesized with a pinned
provider or separately developed with verifiable voice identification.

The receipt records technical integrity **only**. Academic correctness,
spoken pronunciation assessed by listening, and element-level visual
highlighting remain independent release gates. No original lecture
folder, historical MP4/WAV, or production data needs to be modified to
run these offline unit tests.
