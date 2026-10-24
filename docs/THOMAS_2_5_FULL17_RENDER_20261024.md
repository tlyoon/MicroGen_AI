# Full original Thomas Calculus §2.5 technical rendering: 17 slides, 66 cues

24 October 2026. Original package MicroGen_AI, HP only. PR #162 stacked on PR #161.

The source-sha-bound 17-slide cue manifest (1,179 offline recognized words, 66 uniquely matched source PDF words) has been converted to an actual staged lecture via `microgen_full17_render.py`. The generator builds a new isolated workspace, copies all 17 historical MP4-derived WAVs without changing the source, creates measured WAV timing and per-slide PDF cropping, renders all 17 slide videos with FFmpeg and concatenates them to one strict-under-600-second MP4. No source G: Drive file is written.

**Real technical result**: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_full17_provisional_render_PR162\part01.mp4`, SHA-256 `fba8a3b7c423ba7a63a4c1a33661967769947b2f28cb9b84d50551197612fdcb`. Full candidate is source-verified, video exists and duration acceptance is under 600 seconds, but the separately recovered ~1.023-second historical AAC/audio tail is not included in this first multipart composition. The audio is a legacy MP4 reconstruction, NOT individual original generated TTS WAVs. Its known slide-6 `c.`/“circa” and slide-10 `y` defects are NOT corrected in this version, and mathematical formula/figure narration highlighting remains incomplete.

The next planned stage must remux with a bit-identical decoded PCM audio master that preserves the tail, and retest visual timing. In no circumstances does this demo authorize publication or replace original lecture video files. No paid APIs, Whisper, Dell-115, Yoga 6 or protected-main modifications.
