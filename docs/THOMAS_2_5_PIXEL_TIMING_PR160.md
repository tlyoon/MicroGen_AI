# PR #160 — Independent visual-pixel timing verification, original MicroGen_AI

The new `microgen_offline_highlight_pixel_qa.py` accepts a SHA-bound, nonpublishing candidate from PR #159, the original source PDF and an explicitly selected local FFmpeg executable. It samples video frames before and during **every candidate ASR word cue**, crops the region from the actual original-PDF text geometry mapped into the 1280×720 encoded video, and requires a meaningful pixel change within the intended highlight region. The video and original-PDF checksums are verified before and after. No original teaching file or candidate MP4 is rewritten.

## Real Thomas Calculus §2.5 check on HP

Real receipt results were written inside the isolated HP technical-candidate directories under `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_asr_highlight_pilot_PR159`.

| Trial | Word | Mean before/during RGB pixel difference |
|---|---|---|
| Slide 5 C-dot | formal | 24.5857 |
| Slide 5 C-dot | interior | 16.2041 |
| Slide 5 C-dot | continuity | 25.8651 |
| Slide 6 C-dot | discontinuous | 21.4462 |
| Slide 10 Y-value | closed | 18.3470 |
| Slide 10 Y-value | interval | 18.6135 |
| Slide 10 Y-value | discontinuity | 15.8785 |

All seven regions exceeded the test threshold of 2.5 RGB intensity units. This confirms that the implemented source-PDF overlay was **visually present at the ASR-assigned time**. The verifier refuses altered video hashes, corrupted PDF provenance, missing rendered cues, unexpected frame sizes and overwritten reports.

## Critical limitation

This is only physical pixel verification, not independent acoustic word identity. Vosk timestamps may be wrong even at confidence 1.0. Only a small subset of uniquely matched content words is highlighted; the system does **not** yet identify the formula, figure or graph corresponding to every spoken phrase. Likewise, the trial `c.` and `y` recordings are not independently approved as correctly pronounced or same-voice, and academic meaning is not certified. No full 17-slide synchronized lecture has passed release acceptance. The result must remain `publication_allowed=false`. No paid provider calls, Whisper, GCS lease, Moodle/YouTube publication, Dell/Yoga testing or protected-main modification.
