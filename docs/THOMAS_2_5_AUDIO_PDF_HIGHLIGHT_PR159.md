# Source-bound acoustic word-to-PDF highlighting pilot, Thomas Calculus §2.5

This PR implements `microgen_offline_asr_pdf_highlight.py`. It proposes only PDF words that occur **exactly once** both in the source slide and in the explicitly SHA-bound offline-recognized candidate audio. Candidate recognition confidence must be at least 0.90; any variable with fewer than five letters, repeated PDF/ASR word, excluded structural stopword, missing geometry or out-of-range audio time is omitted. Words are highlighted using their actual source-PDF rectangles and the Vosk-produced candidate-audio local clock, never estimated narration percentages.

## HP real pilot

Source original `slides.pdf` is the same 17-slide §2.5 lecture as in PRs #154–#158; SHA rechecked unchanged. Three **isolated, nonpublishing** MP4 technical candidates were rendered from the previously recorded correction WAVs:

- **Slide 5 (C-dot trial)**: 38.46-second MP4 with unique-word highlights `formal` (2.55 s), `interior` (7.41 s) and `continuity` (21.39 s).
- **Slide 6 (C-dot trial)**: 32.10-second MP4; `discontinuous` is the only uniquely matched high-confidence content word at approximately 30.18 s.
- **Slide 10 (Y-value trial)**: 32.92-second MP4; `closed` (14.22 s), `interval` (14.79 s) and `discontinuity` (23.94 s).

Candidate MP4s and receipts are under `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\2_5_asr_highlight_pilot_PR159`, not under the source G: teaching folder. All are under 600 seconds. Nothing was published or merged.

A subsequent independent pixel sampling of the FIRST highlighted word in each video compared frames before and during each acoustic ASR cue. Mean RGB differences within the grounded text bounding boxes were 24.586, 21.446 and 18.347, respectively (for slide5 `formal`, slide6 `discontinuous` and slide10 `closed`). This confirms timed highlight **pixels appear**; it does not prove that an ASR-recognized word was actually articulated at the timestamp or that the text is the pedagogically relevant equation/figure.

## Constraints

Model transcript timestamps and confidence are **not** independent ground truth. Only isolated content words are highlighted, not full mathematical formulas, graphs, figure panels or every narration element. C-dot and y-value phonetic correctness, single-voice integrity between historical reference audio and unapproved correction WAVs, human listening QA, math correctness and final full-lecture synchronized composition remain unverified.

The next crucial step is a spatial/semantic source-and-narration alignment method that can identify the specific formula/figure panel referenced by each spoken phrase, with fail-closed behavior on ambiguity. Do not claim full production completion or release readiness based on these isolated pilots.
