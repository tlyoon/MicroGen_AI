# PR261 — Independently sourced significant-figure computation QA

## Scientific gap

PR249 validates necessary L/M/T dimension equalities, PR251 checks original-source SI unit relationships, PR255 verifies source-backed speed-limit conclusions, and PR257 checks an original figure-based tangent-height example. The new original ChatGPT-authoring campaign for Serway 1.6 Significant Figures contains a different scientific requirement: do not report calculator product digits beyond what the least precise measured input permits.

## New source-tied typed arithmetic

New microgen_private_source_significant_figures.py supports an explicit optional list source_significant_figure_claims in the private lesson manifest, for one narrowly supported operation: rectangular_area_m2. For each typed claim it independently reconstructs original bounded PDF source passages from the original file, confirms the SOURCE PDF SHA, page, passage IDs and literal anchor, verifies the original measured values with metre units and the original reported area with square-metre units, and checks that the claimed value is actually spoken on the declared slide. It computes the product in bounded Decimal arithmetic, counts significant digits including written trailing decimals, rejects ambiguous integer trailing zeros and invented/unsupported numeric values, and rounds to the least significant-figure count using the declared ROUND_HALF_EVEN rule.

It is NEVER arbitrary Python evaluation, arbitrary scientific formulas or semantic claim approval. Unknown operations, forged PDF/slide citations, false numbers, wrong/extra reported precision and outputs missing from original narration FAIL BEFORE rendering. Contracts with no such opt-in claims remain backward compatible with zero verified claims.

Integrates source-verified per-slide original_source_significant_figures_evidence and total source_verified_significant_figures_claims_count into existing slide and video technical receipts. The PR256/257 standalone science audit and PR259 unified private campaign now recompute exactly the same quantitative proof instead of duplicating an algorithm.

## Real first-time Serway 1.6 source / lecture validation

Read-only original PDF G:\My Drive\Serway\Serway_1_7\1\1.6\source.pdf SHA 4045e791d20868b1e492670efa2aeb39455719ffca68c86f27364b122882db40. PR260 had already created original ChatGPT-authored ten-topic source-anchored manuscript and passed a complete private candidate video independent postflight. This PR copies that already accepted original narration/source/contract into a FRESH PRIVATE stage, adding one typed opt-in claim on slide 10, without altering textbook original, ChatGPT-authored text, images, WAV or published material.

The claim links original source passage IDs p03_020_e40940c1fb and p03_021_cd3ec983ed, original source page 3 and the original narration on slide 10:
- Room length 12.71 m — 4 significant figures.
- Room width 3.46 m — 3 significant figures.
- Exact Decimal product 43.9766 square metres.
- Rounded reported value 44.0 square metres, THREE significant figures, preserved trailing decimal zero.

The original PDF contains every declared measurement and final result, and the unmodified lesson narration actually reports the stated area. The private NEW ten-slide source-typed PDF was fully re-rendered and passed:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR261_SERWAY16_SIGNIFICANT_FIGURES_TYPED_SLIDES\slides_teaching_candidate.pdf
SHA 90aa11cb950aa399033969eb71c8a2500d1954db736913b24a016cbd93f9b3a0.

The PR259/260 expanded five-section atomic unified source+science campaign independently PASSED with this new source-typed proof:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR261_FIVE_SECTIONS_TYPED_SCIENCE_UNIFIED_PRIVATE.
The previously independently verified PR260 10-slide, 375.814-second internal media remains available privately; unnecessary repeated audio generation was intentionally avoided on small HP. This new change only alters source-typed technical QA/slide receipts, NOT the original voice/audio files. New media would require its own independent postflight if generated.

## Regression and acceptance

Synthetic test_microgen_private_source_significant_figures.py includes correct original synthetic-PDF source and narration verification, significant zero semantics, malformed/nonfinite/false numeric claims, incorrect rounding, forged source SHA/page/passage/citations, unsupported operations, and untouched optional legacy contracts. New tests plus existing unified-campaign tests: 34 PASS.

Permanent owner restrictions: original MicroGen_AI development/testing on authorized HP only, ChatGPT/Gemini authoring only, NEVER install or use a local language model, unapproved paid API or copyrighted textbook upload. Source and candidate media private; no full academic correctness, copyright permission, phoneme precision, formal narrator or publication approval.

Require full HP root pytest success and ALL FOUR GitHub Ubuntu/Windows Python 3.11/3.12 CI matrix jobs success on the exact PR head before squash merge. Next candidate: generalize the guarded source-backed measurement and rounding rule only after a separate independently verified real-section need; never relax to unverified broad semantic AI approval.
