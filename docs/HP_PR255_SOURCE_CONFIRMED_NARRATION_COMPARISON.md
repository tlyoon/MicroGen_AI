# PR255 — Source-confirmed spoken speed-limit polarity QA

## Existing context

PR251 checks that an opt-in source-cited SI speed inequality is numerically true, with strict rounding uncertainty. PR252 independently checks explicit spoken equality of quantities in different units, and PR253–254 provide conservative evidence/coverage triage. These are not full scientific semantic checking. The new risk is a clearly *reversed conclusion* in a ChatGPT/Gemini-authored narration, e.g. a claim that the driver is BELOW the speed limit after the source and independently calculated SI comparison establish that the driver EXCEEDS it.

## Scoped mechanism

New microgen_portable_scientific_comparison_polarity.py checks only a **definite, positive/negative driver/car/vehicle vs posted speed limit statement**. It requires:
- The opt-in typed source_unit_conversion_claims record already passed PR251's independent original PDF/source SHA/page/passage/value/unit/inequality verification.
- The very same source_comparison_anchor (already source-verified by PR251) has an unambiguous definite driver-vs-limit conclusion consistent with the actual strict SI direction.
- The authored narration on that same slide contains an equally unambiguous definite driver-vs-limit conclusion. If it contradicts the supported direction, fail before PDF/WAV/video rendering.

Examples checked: a narration that the driver is found to exceed the limit agrees with source stating the driver is indeed exceeding the speed limit and with 38.0 m/s greater than 75.0 mi/h. A changed narration saying driver is BELOW, UNDER, WITHIN, or NOT EXCEEDING the limit fails. A source anchor that says NOT EXCEEDING cannot be used to assert exceeding even though prior numeric SI matches.

To avoid false stopping: hedged, hypothetical, interrogative or unrecognized narrative wording is ignored **and NOT counted as verified**. This is narrow, source-grounded claim-level logic, not AI interpretation. Unknown physics, complex discourse, double negatives, conditional cases and absent typed source comparisons are left unverified. Source excerpts and protected text never leave the authorized HP.

## Integration and provenance

Integrates into the portable slide renderer after PR251 verifies typed original PDF SI facts, alongside prior PR247 source gate, PR249 L/M/T dimensional relation checker, PR252 literal narrated numeric unit equality, and PR253 coverage triage. Adds per-slide source_comparison_spoken_polarity_evidence and aggregate source_verified_spoken_speed_limit_conclusions_count to slide and portable video receipts. A checked conclusion is NOT complete academic correctness.

Tests: wholly synthetic test_microgen_portable_scientific_comparison_polarity.py covers true direction, false below/under/within/not-exceeding directions, false source anchor, reverse less-than correct/incorrect conclusions, optional/absent typed claims, unsupported words, and hypo/question/metatalk nonblocking. Focused tests 22 passed.

## Real Serway 1.4 pilot

Reused original private §1.4 PR251 source and six-topic ChatGPT-authored narration; read-only original source PDF retains SHA 9dc28034e807304e242101d066790068477865f19d9a4bc04e5e474c2f7df3c5. A new private six-slide teaching PDF was rendered with three original-source typed SI claims, one automatic spoken numerical SI equivalence, and **one independently source/SI-concordant definite driver-exceeds-limit conclusion**. Fresh private PDF SHA 2291affd5a7d62a099acac5f25e1e3142168407e9253c1f6f5ae15cef06b9a26.

Private output: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR255_SERWAY14_SOURCE_POLARITY_SLIDES.
No original textbook passage, figure, audio, or private lectures are committed to GitHub. Source rights, production voice authorization, scientific coverage and publication approval remain false. This QA uses no local language model, no provider API and no other device.

Next recommended milestone: regenerate an *independent multi-section semantic-QA campaign receipt* that accepts source-approved typed contracts and narrations, includes explicit proven vs unproven claim counts, and rejects deliberately contradictory current-stage source conclusions without rebuilding whole audio/video; avoid duplicating earlier broad coverage work. All future PRs require full HP pytest and four GitHub Windows/Ubuntu 3.11/3.12 jobs green on exact head, and a clean synchronized main.
