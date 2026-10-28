# PR #206 — Offline media continuation without unnecessary ASR/TTS retries

Original `tlyoon/MicroGen_AI`, **HP-only**, stacked on exact PR #205 head `1935da53a581516d049e1767933d22856f9c46d1`. No source or production media overwrite, other PC access, paid providers, Whisper, Moodle or YouTube publication.

## Previously observed development stall

Even after PR #204 relaxed **media-generation progression**, the unattended TTS campaign entry point still invoked strict paid-ASR preflight before acting, requiring original source-stage `slides.mp4` and two independent recognition passes. Real Thomas §2.5 instead has **two valid sub-600-second MP4 parts**, and a recognizer outage should not prevent continued generation when source-bound WAV provenance and structural audio quality pass. The user requested that minor audio-QA uncertainty not consistently stop development.

## Integrated solution

`microgen_tts_autonomous_campaign.py` now supports `--continue-without-asr` for a **bounded, zero-recognition-call** read-only continuation:
- Uses `audit_stage` for technical source/WAV/voice/PCM and optional exact multipart AV receipts, and the separate `audio_generation_progression` from PR #204.
- Blocks **verified critical** WAV, input/voice provenance, reviewed lexicon or severe known math-phoneme red flags; refuses mismatched or only-one multipart receipt and refuses reuse/overwrite of any existing QA folder.
- Runs the normal `run_qa_campaign` without acoustic recognition, preserving all source-bound risk flags, immutable WAV identities, generated listening clips and independent strict final release report.
- Exports honest `OFFLINE_NO_ASR_NO_TTS_BILLING`, `CONTINUE_WITH_ADVISORIES`, `publication_allowed=false`, `independent_phonetics_verified=false`. Exit success is **media workflow readiness only**, never scholarly or phonetic certification.
- Also wires explicit multipart receipts through the original paid-ASR preflight and campaign, resolving the incorrect single-video precondition **without** weakening the paid recognition path or strict final acoustic acceptance.

### Reproduction with original HP Section 2.5

```powershell
python microgen_tts_autonomous_campaign.py "<HP isolated source stage>/2.5" "<new separate HP QA output>" --continue-without-asr --multipart-receipt "<HP existing highlighted_part_receipt.json>" --multipart-independent-av "<HP independent_pixel_pcm_receipt.json>"
```

The pilot has 23 original narration WAVs, two technical-valid MP4 parts (464.67s and 445.88s), 69 flagged mathematical-letter source expressions and 69 listening-review clips. **No synthesis or new video render** occurs in this command.

After a successful technical continuation, next code-development acceptance requires actual spoken mathematical expression checks and element-level figure/equation synchronization, plus at least one independent textbook subchapter pilot. No publication before those are supported by evidence. Draft integration and main-branch merge are separately controlled; this change is not codebase-completion or teaching-quality certification.
