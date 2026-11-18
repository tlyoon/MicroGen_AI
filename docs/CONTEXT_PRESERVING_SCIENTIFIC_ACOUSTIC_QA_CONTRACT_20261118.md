# Context-Preserving Scientific and Acoustic QA — Binding Development Contract

**Effective:** 18 November 2026
**Project:** original API-based `MicroGen_AI`, HP-only, not Selenium `MicroGen_AI_Web`
**Status:** mandatory amendment to the Release Closure Development Contract v1.0/v1.2 and the autonomous scientific/acoustic QA rules.

## Purpose

MicroGen must teach correct physics, not reproduce an LLM reviewer’s preferred wording or accent. QA must accept harmless differences in pronunciation, grammatical inflection, accent, word choice, filler, or explanatory phrasing **when the physics and overall educational meaning remain intact**. A minor difference is not by itself grounds for speech regeneration, a repeated paid review, or a blocked milestone.

## Three severity outcomes

1. **Pass — meaning preserved.** Distinct spellings or pronunciation, natural accent, `multiply by` vs `multiplied by`, `is equal to` vs `equals`, regional unit spellings, or transparent paraphrase retaining the same physical claims, numbers and operators. Retain independent comparison and original evidence; advance automatically.
2. **Advisory — uncertain or minor presentation issue without confirmed contradiction.** Scientific QA records the issue and continues without automatic correction, provided the source-grounded reviewer found no meaningful scientific error. For acoustic QA, do not infer a defective WAV solely from an ASR disagreement; use bounded source-blind independent confirmation only when it is justified by the exact evidence and authorized. Avoid automatic TTS regeneration for mild accents or one-off ASR disagreement.
3. **Block and repair — substantive deviation.** Changed physical claim, numerical value, mathematical operator, sign, exponent, coordinate, unit, equation, causality, direction, negation, or a materially misleading explanation. An uncertain omission of a critical operator such as `divided by` cannot be waived as a small edit-distance change. A confirmed material defect requires source-grounded targeted repair and independent re-verification; uncertain expensive external effects remain a finite hold.

## Executable requirements

- The source-grounded scientific reviewer receives the meaning-first status contract. Existing `pass`/`advisory`/`error` schema remains valid. Only wholly source-cited, byte-verified, narrowly proven equivalent `error` rows may be downgraded to `advisory`; mixed or unsupported claims remain blocking.
- The source-blind two-Gemini acoustic QA normalizes only explicit established equivalences. Canonicalization may not erase an equation operator, alter a number, remove negation, conflate variables or discard units. Never globally increase word-error budgets as a substitute for evaluating meaning.
- Historical failed reports are **evidence**, not permanent failure classifications. Re-evaluate saved exact source/WAV-bound transcripts under the present tested comparison policy, preserving all original receipts. Only remaining material discrepancies are eligible for new correction/retake; a corrected comparison policy does not authorize repeating an already rejected paid request.
- QA evidence and the context policy must remain pinned to the actual implementation and source inputs. New or changed scientific/scalar claims still require actual independent scientific and acoustic checks. An acoustic transcription is not proof of the original WAV's pronunciation.
- The repair lifecycle is mandatory: **historical failure review → targeted remedy → real-source test → fault-injection/regression → executable recovery registry → normal pipeline restart and automatic forward progression**.
- Preserve finite TTS/ASR request budgets, provider authorization, source/media SHA hashes, independent QA, 600-second maximum per delivered video, actual decoded visual synchrony, nonpublication and G1–G4 release boundaries.
- Never call original `MicroGen_AI` code on Dell-115; HP is the designated device. Do not merge a candidate or declare G3/G4 accepted without fresh pinned-code real evidence.

## Historical acceptance fixtures (Serway §2.7, 18 Nov 2026)

- Slide 7 reviewer A source-exact; reviewer B heard `multiply` instead of `multiplied`. This is meaning-preserving morphology in `multiply by` and is **not a TTS repair** when all other source checks pass.
- Slide 5 reviewer A source-exact; reviewer B twice omitted `divided by` in the equation narration. Because the missing operator may change mathematical meaning, it **remains unresolved** until independently established as a transcription artifact or corrected source-bound speech. Neither word-count ratio nor the correctly printed slide alone proves the audible operator exists.

## Implementation and validation

`microgen_context_qa_tolerance.py`, `microgen_autonomous_science_qa.py`, `microgen_tts_acoustic_qa.py`, `microgen_one_sided_acoustic_replay.py`, `microgen_tts_evidence.py`, and `microgen_recovery_registry_v6.json` are the executable enforcement points. `tests/test_microgen_context_qa_tolerance.py` and the existing science/acoustic/history recovery test suites verify both accepted minor variation and blocked materially wrong physics. Test approvals never represent actual independent model evidence or public publishing authorization.
