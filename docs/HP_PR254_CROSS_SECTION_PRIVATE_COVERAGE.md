# PR254 — SHA-grounded private cross-section source coverage campaign

## Purpose

PR253's new source passage/topic advisory audit works per ChatGPT/Gemini-authored lecture. Re-running separate full multimedia campaigns for previously authored lessons is expensive on the small HP desktop. This change introduces a LIGHTWEIGHT, read-only, evidence-preserving multi-section verification across private textbook PDFs and the original, privately stored ChatGPT/Gemini response JSON for each section.

## How it works

The new microgen_private_cross_section_coverage.py accepts a **private JSON manifest** of 1–12 source cases. Each must specify unique section_id, original source_pdf path, the exact PR247 private source authoring packet path, and the original authored response path. It independently checks:
- Each PDF is an actual unchanged, nonsymlinked file, and all inputs are hash-frozen.
- Source PDF SHA equals the packet and authored draft SHA, and the draft's claimed packet canonical SHA matches.
- The entire packet is independently RECREATED from the original PDF's start and next-section headings or end-of-PDF boundaries; a forged PDF passage and recomputed fake packet/draft hashes cannot pass.
- The original PR247 authoring validator checks original source anchors/meaningful required terms, source paragraph copying, unknown numerical values, duplicate narration, topic page ordering and figure/numeric crop SHA evidence.
- The PR253 source-coverage semantic-risk profile is recomputed. Only nonblocking high-interest gap IDs, source-page indices, category tags, total discovered/cited and source hashes are retained in the resulting JSON.

If **any** case fails, the whole audit stops without writing a partial output; a fresh PRIVATE receipt directory is atomically published only if all cases validate and input SHA values remain unchanged. Inputs are not overwritten, no media/TTS is regenerated, and no text of copyrighted source or independently authored narration is exposed in the output or in this GitHub PR. A private output under My Drive or a source-containing hierarchy is prohibited.

Example command:

    python microgen_private_cross_section_coverage.py --private-case-manifest <private-cases.json> --new-private-output <fresh-HP-private-output-dir>

The program runs NO network requests, Chrome automation, inference models, Gemini APIs or paid services. It is designed for HP as a small local QA orchestrator.

## Three real original Serway subsections exercised on HP

The verified source packet and independently authored response were reused from prior successful privately generated lessons, without copying textbook materials to public GitHub:
- Section 1.2, source PDF and original PR247 authored response;
- Section 1.3, source PDF and original PR248 independent ChatGPT draft;
- Section 1.4, source PDF and original PR250 ChatGPT six-topic draft.

Private manifest: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR254_THREE_SECTIONS_INPUT_PRIVATE.json
Private audit receipt: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR254_THREE_SECTIONS_COVERAGE_PRIVATE_REPORT\multisection_private_coverage_receipt.json

Result: **3** original source PDFs and draft/packet pairs independently revalidated; **71** source passages discovered, **44** cited, and **9** context-rich uncited passages flagged for *advisory* review. These 9 are NOT proof of missing learning objectives, and 44 cited source passages are not proof of semantic correctness. Source copyright, academic completeness, voice suitability, figure matching and publication rights remain NOT certified.

## Synthetic regression

test_microgen_private_cross_section_coverage.py tests multiple separate PDFs, one-section operation, malformed/missing source, changed originals, corrupted source packet, a malicious forged packet with corrected draft packet checksum, duplicated IDs, copied or invented numeric claims, missing user-authored responses, forbidden private output destinations, and output collision. Existing PR253 coverage integration tests also run, 23 focused tests passed.

Before squash merge, run HP full repo pytest and all four GitHub hosted Windows/Ubuntu Python 3.11/3.12 CI jobs on exact head. Next focus: stricter claim-level semantic comparison using explicit scientific relationships from source and slides, not an unreliable generic AI-generated proof, while keeping user-friendly bounded advisory QA. This package uses ChatGPT or Gemini only for original authoring and NEVER local language models.
