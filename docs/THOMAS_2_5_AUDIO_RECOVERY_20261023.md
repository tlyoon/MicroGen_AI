# Thomas Calculus §2.5 — verified legacy audio recovery candidate (HP, 23 October 2026)

Source: original package `MicroGen_AI`, not `MicroGen_AI_Web`. Developed on HP only from the current PR #153 draft. The original `G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\2\2.5` assets were read only.

## Source evidence and recovery

- Original MP4 SHA-256: `7d27d24d5d6a7ae5bf05cfcef1ea324d628abcf70688437a5555ac1c85b7e9f8`.
- The existing `.microgen_legacy_video_evidence.json` binds that MP4, the current PDF and narration JSON, plus **16 video scene-change timestamps** for 17 slides.
- Original root `slide1.wav` through `slide17.wav` were absent. This did **not** prove no audio existed: the preserved MP4 has AAC audio.
- The new `microgen_legacy_audio_demux.py` validates original checksums and scene evidence, decodes audio at 16 kHz mono PCM16, partitions it into **17 provisional scene-aligned WAVs**, verifies the video was not modified, and emits a source-bound receipt.
- Real isolated HP recovery stage: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_legacy_scene_audio_PR154_v2`. The 17 slide excerpts total **550.23 seconds**. They are not the original TTS WAV files and do not establish word-level alignment.
- Original AAC decoding is **551.253375 seconds**, while MP4 container video duration is **550.23 seconds**. The additional **1.023375 seconds** is separately retained as `audio/audio_after_video_end.wav`; RMS **0.064126**. Its contents (speech, music, trailing noise) are *not* yet classified. The presence of acoustic energy means it must not be silently discarded.
- Both original MP4, original slide PDF and original narration JSON hashes remained unchanged across this run.

## Strict limits

The old audio may contain the reported `c.` → "circa" and `y` pronunciation defects. The independent QA directories include corrected trial WAVs for slides 5, 6 and 10, but they are **not** automatically spliced into this older AAC track: external source-text binding, codec timing, voice consistency, pronunciation quality and slide-highlight synchronization must be resolved first. Recovered scene boundaries are timing estimates for video transitions, **not** verified word/element narration cues.

This reconstruction is a **technical working candidate only**: `publication_allowed=false`, `phonetic_accuracy_verified=false`, `word_alignment_verified=false`. Do not merge/publish/replace historical MP4s without independent QA. Do not invoke paid provider APIs, Whisper, Moodle, YouTube, Dell-115 or Yoga6 for this stage.

## Immediate next development

Measure and classify the overhanging 1.023 s clip by independent listening; devise a non-destructive candidate end-frame extension if necessary. Analyze correction WAV/voice provenance for 5, 6 and 10. Then build a **new**, source-bound synchronized candidate in staging and verify real speech-to-visual cues. Preserve the original lesson untouched.
