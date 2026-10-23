# Thomas Calculus §2.5 — lossless tail-preserving video candidate, 23 Oct 2026

Original MicroGen_AI, developed and tested exclusively on HP. This is a **technical validation candidate, not a publication**.

## Defect and data

The original video `slides.mp4` has SHA-256 `7d27d24d5d6a7ae5bf05cfcef1ea324d628abcf70688437a5555ac1c85b7e9f8` and container duration **550.23 s**. Source AAC decoding gives **551.253375 s**, i.e. **1.023375 s** of additional decoded audio at the end. That extra audio has RMS **0.064126**; audible energy is present but whether it is speech has NOT been independently determined. The original lesson root retains no slide1–slide17 production WAVs.

The first attempt using an AAC packet stream copy and `-shortest` yielded only 550.20 s of video and a different decoded-audio SHA. A second attempt using lossless ALAC but still relying on `-shortest` also stopped at 550.20 s. **Both were rejected** and remain separately identifiable in the isolated staging directory.

The successful implementation verifies every staged original AAC-decoded PCM fragment and appends the preserved end tail, checks the exact reconstructed PCM SHA against the original decoder, creates an isolated last-frame hold with an explicit target length, uses **ALAC** to preserve the decoded PCM losslessly, and then rechecks the candidate's entire decoded audio SHA.

## Actual accepted technical candidate

- Original video duration: **550.23 s**.
- Decoded original PCM duration: **551.253375 s**.
- New candidate video duration: **551.25 s**, strictly less than 600 s.
- Exact original vs candidate decoded PCM hash comparison: **PASS**.
- Candidate video SHA-256: `93d2b06667b77d7a83e4231890ea42e26a5fbace12a9e2a0cab26f1cbd875fca`.
- Candidate location on HP: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_legacy_scene_audio_PR154_v2\technical_candidate_lossless_timed\slides_full_audio_ALAC_NOT_PUBLISHED.mp4`.
- Original video SHA after processing: **unchanged**.
- ALAC-in-MP4 is intentionally used for lossless technical QA; player/platform compatibility and standard AAC distribution are **not** certified.
- Pronunciation corrections (`c.` and `y`), genuine word-to-highlight synchronization and academic/mathematical figure QA: **NOT verified**. No publication permitted.

The source video and all historical WAV/PDF assets were untouched. All outputs are in isolated HP AppData. No paid TTS calls, Whisper, protected-main edits, Dell-115/Yoga6 access, Moodle or YouTube publication.
