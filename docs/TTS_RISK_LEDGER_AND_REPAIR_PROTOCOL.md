# TTS pronunciation risk register and bounded repair protocol

## Motivation
The lecturer independently confirmed that the new Thomas Calculus Section 2.5 Slide 10 WAV correctly pronounces mathematical `y-value` as `why value`. Earlier, the same subchapter had mathematical `c.` spoken as `circa`. Both errors may be silently normalized into *correct-looking* transcripts by audio recognition, so transcript-agreement cannot prove phonetic accuracy.

## Protocol
1. **Identify risk before TTS.** Scan the exact source narration and the normalized *spoken input* for unambiguous math letter compounds (`x-axis`, `y-value`), context-bound `c.`, standalone variables in mathematical clauses, function argument notation (`f(x)`), raw subscripts, Greek glyphs and mathematical abbreviations.
2. **Classify actions, not just words.** Reviewed deterministic rules get `REGENERATE_WITH_EXISTING_REVIEWED_NORMALIZATION_IN_ISOLATED_STAGE`; ambiguous expressions get `REVIEW_AND_AUTHOR_EXPLICIT_TTS_ONLY_TEXT_BEFORE_SYNTHESIS`. Do not guess new pronunciations or rewrite slide mathematics.
3. **Generate a checksum-bound risk ledger automatically.** After `text_to_speech_v25.py` finishes its verified WAV/voice provenance, it also creates an immutable, content-addressed JSON ledger in the TTS cache. The ledger binds every slide's original narration hash, normalized speech hash, WAV SHA-256, real slide-level start/end times, risk codes and safe repair instructions.
4. **Independent, script-blind acoustic analysis.** PR #25 runs two separate recognition configurations. The risk inventory is an additional check: a clean pair of model transcripts cannot clear a vulnerable math expression. Acoustic recognition prompts avoid mentioning specific expected mispronunciations to reduce response priming.
5. **Bounded corrective loop.** For pre-reviewed rules, synthesize corrected *TTS-only* input in separate scratch, preserve the old audio, check that the same pinned provider and voice is used, rebuild timing and video if durations change, re-check hashes, and repeat acoustic validation. For non-reviewed expressions, request a scientifically reviewed spoken form rather than generating speculative corrections.
6. **Targeted listening.** Review the risk ledger by slide. The timestamps are measured *slide boundaries*, not claims about exact word-level timing. Record explicit listening outcomes against an actual audio hash; the previous confirmation of one phrase cannot certify every pronunciation in the lecture.
7. **Publish gate stays closed.** An acoustic model's clean result, successful synthesis, or fixed sample alone is never academic or listening QA. Separate figure and element-highlight checks are mandatory. This PR adds the register and synthesis-time recording, but does not replace every existing production release gate.

## Local read-only command
`python microgen_tts_risk_register.py path/to/script_tts.json --audio-folder path/to/staged/wavs`

This prints source-grounded risk entries without changing any source file. Optional `--report NEWFILE.json` refuses existing paths. On normal isolated lecture generation, the cache additionally retains the immutable risk ledger, including WAV hashes and measured slide-level timing.

## Real Section 2.5 trial
The risk register identified 29 risk instances on 11/17 slides, including both `y-value` examples on Slide 10 and `c.` examples on Slides 5 and 6. These are risk flags and cannot be represented as 29 actual sound defects. Slide 10 was previously corrected and the user confirmed the audible `why value` pronunciation. No production MP4 or historical WAV is overwritten by this PR.

## Important limitations
This risk list is intentionally conservative and will still miss some true pronunciation defects. Speech recognition may be wrong, biased by conventional mathematical syntax, or insensitive to lexical stress and technical phonetics. New expression classes require reviewed rule additions, adversarial regression data and human validation before a claim of improved field accuracy. An independent real-audio benchmark is required to quantify false negatives and false positives, and near-zero error cannot be guaranteed by source-text heuristics alone.
