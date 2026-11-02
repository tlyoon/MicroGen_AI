# PR251 — Independent source-cited SI conversion and strict speed comparison QA

## Why

PR249 verifies physical dimensions of typed formulas but dimensional consistency alone cannot detect a false length conversion or invalid speed-limit comparison. PR250's ChatGPT-authored Serway Section 1.4 lecture introduces units and speed-limit examples. This milestone adds portable, narrow, independently recomputed unit-value source checks with NO local AI model and NO external API.

## New optional typed source unit contract

New microgen_portable_source_unit_conversions.py checks optional source_unit_conversion_claims from a private source-bound lecture contract. Each claim must cite immutable PDF SHA, a real bounded passage ID/page, a literal nearby source anchor, source and target numeric value/unit pairs found in the cited original source, and a matching narration slide page. Supported dimensions and SI definitions are intentionally narrow: length (metre, centimetre, kilometre, international mile, foot, inch) and speed (m/s, km/h, mi/h). The international mile is defined as exactly 1609.344 metres; the printed textbook 1 mile = 1.609 km is validated to the precision of its stated rounded decimal. Numeric parsing is bounded Decimal arithmetic, never evaluation of model-authored Python expressions.

Two independently checked claim relations:
- equal_with_rounding (default): target equals source converted through SI within half a target printed unit in the last decimal place, AND 5% relative cap. Missing/fabricated printed values and values with false dimensional equality reject.
- greater_than or less_than: source must explicitly contain a same-direction comparison conclusion anchor (words such as exceeding or lower); SI magnitudes are compared with a worst-case rounding margin from both stated values, so near-boundary ambiguity fails conservatively.

Unsafe source references, bad source hashes, invented numeric/unit pairs, unknown units, cross-dimension comparisons, multiple claims on a slide, unclear direction, false inequalities, or target values inconsistent with independently defined SI factors fail closed BEFORE a slide PDF is written. Old contracts without these optional claims remain compatible and report zero checked conversions. Technical slide/video receipts carry a per-slide unit proof and aggregate count. This does NOT prove all scientific claims or copyright rights.

## Actual Serway 1.4 new ChatGPT-authoring campaign

Private read-only source: G:\My Drive\Serway\Serway_1_7\1\1.4\source.pdf, immutable SHA-256 9dc28034e807304e242101d066790068477865f19d9a4bc04e5e474c2f7df3c5.

Private ChatGPT-original six-topic Stage PR250 was copied to NEW staging area %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR251_SERWAY14_SOURCE_SI_CONVERSION_STAGE, with three new independently source-cited claims:
- Slide 2: 1 mile maps to 1.609 km at source stated precision (rounded length equality).
- Slide 3: 1 inch maps to exactly 2.54 cm (length equality).
- Slide 5: the source's observed 38.0 metres/second exceeds the posted 75.0 miles/hour when converted to consistent speed units, with original source conclusion explicitly cited (strict speed inequality).

All three independently pass; a deliberately false claim equating 38.0 m/s to 75.0 mi/h is rejected even though both numbers and units occur in source text. The new six-slide source-bound candidate PDF SHA-256 is 7c5196c723721f0e2ee69a5152267cbceb9c2a112a373a6dfa3616ec1fd32552, under private %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR251_SERWAY14_SOURCE_SI_CONVERSION_SLIDES.

New wholly synthetic tests test_microgen_portable_source_unit_conversions.py: 21 PASS for valid rounded/exact conversion, valid inequality, false equivalence, wrong direction, hallucinated unit/value, fake source anchor and changed original SHA, wrong narration page, malformed numeric literal/oversized collection. Existing prior PR246 typed math and PR249 dimensional checks remain active. Full HP root regression + four hosted Windows/Ubuntu Python jobs required before merge.

## Guardrails

No installed local language models, cloud provider API calls, or unauthorized computers. Only ChatGPT/Gemini content creation via PR250 handoff and lightweight authorized HP Python QA/audio/video. Source PDF, generated original narration, media and source-evidence packet are NOT committed. Experimental Piper candidate voice is not the production narrator. All publication/rights/academic-certification flags remain false.

Next: independent semantic contradiction and important-topic coverage checks with evidence, in limited nonbrittle scope; do not require manual academic review as a development stopper.
