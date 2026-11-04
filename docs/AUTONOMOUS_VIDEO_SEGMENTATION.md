# Autonomous whole-slide video segmentation — PR #273

Original **MicroGen_AI**, not Selenium MicroGen_AI_Web.

## Contract

Every finished individual teaching video must be strictly shorter than
600 seconds. Do not ask a lecturer to approve any split before autonomous
technical progression. Preserve existing source, slide PDF, WAV and full MP4
outputs; do not repeat scientific or paid TTS generation merely to segment.

## Normal production integration

After the existing `gen_video_v22.py` renders and verifies `slides.mp4`, it
automatically calls `microgen_autonomous_video_parts.render_if_needed` for a
long video. The **existing exact-source slideN.pdf / slideN.wav video cache** is
reused, with every original MP4 segment fingerprint checked against the SHA
of its corresponding PDF and WAV. No model, human approval, Cloud TTS or
copyrighted source upload is needed.

The deterministic, bounded dynamic-programming planner uses whole-slide WAV
durations, no interruption within a slide, a conservative target of 545s,
and an optional title-transition preference to minimize topic disruption.
It selects the minimum number of parts with no missing/reordered/repeated slides,
regardless of PDF section number. A single WAV that cannot fit within the
limit fails with a clear technical error instead of being silently truncated.

Parts are rendered into **private temporary scratch** and undergo real MP4
A/V/duration verification before atomic publication inside the existing
private stage. Existing part files are not overwritten unless an exact verified
receipt permits reuse. Errors roll back newly created parts. The original full
`slides.mp4` is retained unchanged.

The source-bound receipt `.microgen_autonomous_parts.json` contains the
source/pdf/full-MP4/script/WAV hash inventory, actual part durations,
ordered slide IDs and output MP4 SHA hashes. A second validator rechecks
all inputs, source segment cache, continuity, durations and final video hashes.
The normal `microgen_batch.stage_valid("video")` calls this validator when
the complete video exceeds 600 seconds. Shorter videos retain their existing
single-file behavior. No human approval is invented.

## Actual independent acceptance

A fresh isolated copy of Serway Chapter 2.1's 19 source-bound slides,
19 Kore WAVs, full existing H264/AAC MP4 and 19 cached original slide videos
was validated on HP. New output parts:

- `slides_part_01.mp4`: slides 1–10, **301.8s**
- `slides_part_02.mp4`: slides 11–19, **325.9s**

Both are under 600s. Original source, full MP4 and exact original slide/WAV
hashes remained unchanged. The test made **zero** Gemini/TTS/API calls.

Private directory:
`%LOCALAPPDATA%\\MicroGen_AI_Checkpoints\\20261104_HP_PR273_CH2_1_REAL_SEGMENT_TEST_PRIVATE`

## Limitations

Slide-boundary split does not independently prove scientific accuracy or
phonetic correctness, and is not a human semantic certification. Existing
manual scene-manifest mode remains a separately controlled legacy option
until the unified autonomous acceptance gate is completed. Audio transcription
quality and full release acceptance are separate tasks. All media remains
private, and output publication authorization remains **false**.
