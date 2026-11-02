# PR256 — Multi-section source-bound scientific-claim regression without video regeneration

## Purpose

Existing sections can become stale relative to new scientific QA gates as the MicroGen_AI pipeline evolves. PR254 revalidated each original PDF, private authoring packet and original ChatGPT/Gemini draft for **source coverage**, not the later typed scientific proofs. PR255 added independently sourced spoken speed-limit conclusion polarity detection. This PR independently rechecks current *scientific consistency* gates across a set of historical private section contracts and scripts on lightweight HP without regenerating heavyweight slides, TTS or video.

## Source + claim contract

New microgen_private_multisection_scientific_claim_audit.py accepts 1–12 explicit private stage cases (section_id, original_pdf, stage). It refuses symlinks/absent or oversized inputs, section drift, stale/forged original source PDF SHA, modified stage source, stale narration/visual contract, approval flags or destination collisions. Runs the EXISTING portable academic structure contract against source.pdf/narration.json/plan.json/contract.json, then independently recomputes:
- PR249 safe AST source-typed L/M/T dimensional equalities with exact original PDF source page/passage/technical-term checks.
- PR251 verified original source-cited SI unit equalities/strict inequality and quantitative rounding tolerances.
- PR252 bounded explicit numeric unit equalities actually spoken in narration.
- PR255 definitely asserted driver-exceeds-vs-below-source-limit conclusion polarity, only following prior independent PR251 SI proof.

A single failed item rejects the ENTIRE campaign; no partial receipt is published. Inputs are SHA-frozen before/after. A successful fresh PRIVATE report contains only section ID, source/contract/narration hashes and numerically checked claim counts; NO copyrighted source text, narration text, figures, voice weights, video or other protected assets. No provider access, ChatGPT/Gemini call, paid API or local language model; only ordinary authorized HP Python processing.

**Important limitation:** PR246 optional source-cropped figure/equation *typed math* proof is separately implemented and is deliberately NOT rechecked in this narrowly scoped source-stage validator. Each section report explicitly has typed_math_claims_from_other_pipeline_checked=false. Not all mathematics or scientific semantics are verified; no copyright/voice/academic completeness/publication approval.

## Previously authored real Serway regression campaign

Three original section source PDFs, stages and original narrations were independently rechecked:

- Section 1.2, 16 original topics; 0 PR249 dimensional, 0 PR251 SI, 0 PR252 explicit spoken unit relations; PR246 original typed math not included in this pass.
- Section 1.3, 7 original topics; 3 independently source-linked L/M/T dimensional equalities.
- Section 1.4, 6 original topics; 3 independently source-linked SI conversion/strict comparison claims; 1 explicit spoken SI unit equivalence; 1 sourced definite speed-limit conclusion matching the SI comparison.

All source PDF/contract/narration hashes unchanged. Original private source textbook PDFs remain in G:\My Drive\Serway\Serway_1_7\1; the private validated stages are in %LOCALAPPDATA%\MicroGen_AI_Checkpoints. The real campaign report is PRIVATE under %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR256_THREE_SECTIONS_SCIENCE_PRIVATE_REPORT\multisection_private_science_receipt.json. Total 3 source-typed dimensions, 3 source-typed SI relations, 1 automatic narrated SI equivalence, 1 source-confirmed spoken speed-limit conclusion. These counts are **not** a universal objective or semantic-coverage score.

The synthetic regression suite tests two independent real PDF fixtures and stage contracts; parent/source mutation, forged or stale contract/narration, duplicate/missing/out-of-scope section, output collisions, fresh output publication, and deliberately false spoken SI equality. New focused tests 15 passed while kept outside git until PR255 merged.

## Next priority

Extend this audit to include PR246's original typed equation/diagram mathematical claims on §1.2, using the existing safe original PDF geometry and numeric semantics without duplicating validation code, and keep the result scoped and false-positive resistant. All new PRs require full HP pytest and all four GitHub CI Windows/Ubuntu Python3.11/3.12 jobs green on exact head before squash merge, then synchronize clean HP main. All source and media remain private, and only ChatGPT/Gemini may be used for content generation.
