# PR252 — automatic high-confidence unit equivalence checks in lecture narration

## Problem

PR251 validates declared SI unit conversion claims against exact original PDF passage evidence. A generator could still write an incorrect, explicit numerical unit equivalence directly in spoken narration without declaring a typed claim. This milestone adds a **narrow automatic numerical equality scanner** for authored teaching narration before any WAV/video is produced, using NO AI model and NO external service.

## Implementation

The new microgen_portable_narration_unit_equivalence.py recognizes only explicit, unambiguous equality-like phrases such as "one mile corresponds to 1.609 km" or "38.0 meters per second equals 85.0 miles per hour". It uses a bounded regular-expression parser, a small map of common English unit aliases, exact SI definitions already introduced in PR251, and Decimal arithmetic. It independently recomputes the conversion and accepts target values within half a printed decimal unit and a 5% relative cap.

An explicitly wrong equivalence (e.g., declaring 38.0 m/s equal to 75.0 mi/h, or 1 mile to equal 2 km) **fails closed before rendering**. Cross-dimensional equivalences fail. Natural-language statements without a high-confidence equality grammar (questions, inequalities, unrelated numbers, uncertain phrasing) remain unmodified and are NOT claimed checked. This avoids broad false rejections and endless automatic correction loops.

Supported common length and speed names include miles, kilometres/kilometers, inches, centimeters, feet, metres/meters, and speed expressions miles per hour, kilometers per hour and meters per second. The authoring narration is never evaluated as code. No native model, Ollama, paid Gemini API or other machine is involved.

The source-bound slide renderer now always checks narration statements in addition to PR247 source-anchored topical audits, PR246 typed numeric math, PR249 dimensional algebra, and PR251 typed SI conversions. Receipts report the number of automatically verified narrative unit equalities and include a per-slide audit; the full candidate video receipt carries that count as well. Legacy source stages without recognized statements remain compatible with an accurate count of zero.

## Real Serway 1.4 proof

The NEW ChatGPT-authored six-topic Section 1.4 private narration from PR250 and three source-cited SI claims from PR251 were re-rendered without changing their original source or narration. The scanner independently found and verified one native English narration equivalence on slide 2. Its numeric 1-mile/1.609-kilometre relationship agrees with independently defined SI factors at the printed precision. Three existing explicitly source-cited unit statements (slides 2, 3 and 5) also verified.

Private six-slide teaching PDF SHA-256: 45c1305d2059211d8eb935947a3f368e8088528ea849813c119693529c175c1f.
Private output: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR252_SERWAY14_AUTOMATIC_NARRATION_SI_SLIDES.
Original source PDF unchanged SHA-256: 9dc28034e807304e242101d066790068477865f19d9a4bc04e5e474c2f7df3c5.

Synthetic test_microgen_portable_narration_unit_equivalence.py includes 14 focused PASS, covering correct rounded conversions, false length and speed equivalences, cross-dimension errors, singular/plural aliases, and non-equivalence phrases. Full authorized HP root tests and four GitHub hosted Ubuntu/Windows CI jobs are mandatory on the exact PR head.

## Boundaries

This linter cannot interpret arbitrary English, determine whether source PDF actually supports an untyped statement, certify omitted mathematical concepts, or guarantee all scientific assertions. Its receipt explicitly says source text provenance and full physics semantic correctness are NOT proven. All output remains private, copyright and production narrator rights are not cleared, and publication_allowed=false. Content generation remains ChatGPT or Gemini only; **never introduce locally installed AI language models**.
