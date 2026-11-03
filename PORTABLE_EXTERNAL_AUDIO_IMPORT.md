# Source-aligned, no-model WAV import

This accepts **pre-existing** WAV files from a separately authorized
voice-generation workflow. It never invokes or installs a local language or
speech model, calls a provider, bills an account, or chooses a default voice.

First run `microgen_portable_voice_input_handoff.py` to create a verified
private narration request bundle. Next, generate a private template:

```text
python microgen_portable_audio_import.py \
  --private-handoff PRIVATE_VOICE_INPUT.json \
  --new-private-template NEW_PRIVATE_CAPTURE_TEMPLATE.json
```

A later *authorized* voice workflow must create exactly `slide01.wav`, ...
in one private folder, using each exact request text. Set the manifest's
`declared_provider`, `declared_voice`, and each `wav_sha256` from the
actual files. The audio import command then runs:

```text
python microgen_portable_audio_import.py \
  --private-handoff PRIVATE_VOICE_INPUT.json \
  --audio-dir PRIVATE_RECORDED_WAV_DIR \
  --capture-manifest PRIVATE_COMPLETED_CAPTURE_MANIFEST.json \
  --new-private-receipt NEW_PRIVATE_PCM_VERIFICATION.json
```

The import checks SHA256 of the unmodified voice handoff, exact slide/text
identity, filename inventory, WAV bytes, mono PCM16 structural quality,
length, and immutable inputs. It does **not** prove the advertised provider,
speaker, actual spoken words, acoustic pronunciation, rights, or suitability
for publication. A declaration is not authorization.

For preview-only A/V muxing after actual WAV acquisition, reuse the existing
offline diagnostic mux path and preserve its unapproved diagnostic labels.
Do not make a locally generated speech candidate the formal/default narrator.
Do not commit source speech, private WAVs, provider secrets or manifests
containing protected text to GitHub.
