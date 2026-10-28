# Mathematical letter-name speech: Y versus yay

## Confirmed problem and scope
The user heard the variable **y** pronounced as **yay** near 4:54 in the Thomas Calculus 2.5 review video. Slide 10 contains two occurrences of `y-value`. The source narration and slide should continue to show `y-value`; the **audio-only** input is spoken as `why value`.

## Deterministic corrections
The normalized TTS input now expands only unambiguous math/coordinate compounds with single-letter `x` or `y` followed by a dash and a recognized noun. The letter names are `ex` and `why`, with examples `y-value`, `x-axis`, `y-coordinate`, and `x-intercept`. Unicode dash variants and plurals are supported. No global replacement of letters, English words, mathematical diagrams or human-readable source narration is permitted.

## Acoustic detection
Independent spoken-audio QA (PR #25) now flags a transcription containing `yay` where the expected token is the letter `why`, even if the overall token mismatch percentage is below 5%. This is in addition to the earlier `circa`/C red flag. The recorded audio still needs human listening verification; text normalization is a prevention technique, not an acoustic guarantee.

## Safe regeneration
Check the slide source hash, expected TTS provider and voice, regenerate the *affected* WAV in isolated local scratch, and verify duration, format and voice consistency with other WAVs before rendering a new, **non-published** review MP4. Preserve old WAV/MP4 and do not silently push replacements to a course. Re-run audio-visual QA and obtain listening approval before any release.

## Wider policy
Future one-letter mathematical variables outside the tested coordinate compounds should be flagged for lexicon review instead of substituted globally. CI synthetic/fixture checks and a real audio listening suite are both required to approach low mispronunciation rates. No finite test suite can guarantee zero mispronunciations.
