# PR259 — Atomic unified private source and scientific QA campaign

## Motivation

PR254 independently recomputes source-passage authoring and advisory coverage. PR256–257 recompute typed scientific, mathematical, source-figure and spoken-consistency proofs. Running these separately required manually translating one case manifest into another and could leave an apparently successful source-coverage receipt with an unmatched or failed scientific pass.

## New unified workflow

microgen_private_unified_campaign.py takes an explicitly private JSON manifest with 1–12 cases, each containing: section_id, source_pdf, private_packet, private_draft and stage. It invokes BOTH pre-existing independent validators on exactly the same source PDF and section ID. It checks they agree on exact original PDF SHA-256 and number of authored topics, then emits one new atomic PRIVATE directory containing:
- coverage/multisection_private_coverage_receipt.json
- science/multisection_private_science_receipt.json
- unified_private_campaign_receipt.json (cross-gate source identity, counts and cryptographic hash of each sub-receipt)

**All-or-nothing:** no final receipt directory exists until both validators pass for every section, source identities and topic totals agree, and all original input hashes remain stable. A failed second validation removes the temporary receipts automatically. The tool refuses duplicate or missing sections, forged packets, stale original PDF or stage source, modified narration/contracts, unsafe output inside original source or stage directories, output collisions, symlink input or protected figure drift.

This does not regenerate audio, slides or videos, does not invoke ChatGPT/Gemini or any language model, and has zero paid cloud API or extra computer use. The only information retained is privately stored source identifiers, hashes, counts and advisory QA category labels; no textbook or narration excerpts, figure files or voice assets. Nothing is published.

## Real four-section validation on authorized HP

Original source PDFs and independently authored private responses for Serway §§1.2, 1.3, 1.4, 1.5:
- **4 independent section and source lineages**
- **36 authored teaching topics**
- **86 bounded original source passages discovered, 58 cited**
- **9 high-interest uncited passages** for *advisory*, not proven missing educational objectives
- **4 source-PDF pixel-identical figures**, **1 original vector-equation crop** and **1 independently source-calculated mathematical claim** (earlier §1.2 tree height)
- **3 dimensional equalities**, **3 typed SI relations**, **1 spoken SI equivalence**, **1 source-verified spoken speed-limit conclusion**
- All original source hashes unchanged; no complete scientific certification, copyright rights, formal TTS voice or publication approval.

Private manifest:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR259_FOUR_SECTION_UNIFIED_MANIFEST_PRIVATE.json

Private unified, source, science receipts:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR259_FOUR_SECTION_UNIFIED_RECEIPT_PRIVATE

## Synthetic regression

Tests test_microgen_private_unified_campaign.py cover two synthetic genuine PDF/packet/draft/stage bundles, the source and scientific receipt hash cross-links, absence of source words, immutability, forged packets, modified source/contract/narration, duplicate/swapped cases, protected directories, and atomic failure. During development, a test caught destination nested inside a protected stage; the new protected-stages guard was implemented and the test now passes. All 13 tests pass.

For acceptance, run full HP repository pytest successfully and hosted GitHub Actions matrix for Ubuntu/Windows Python 3.11/3.12 on exact branch commit before squash merge. No textbook source files or authored media in the PR.

## Owner's permanent policy

Only HP desktop for original MicroGen_AI development; never install or run a local large language model. Original content generation only through ChatGPT or Gemini, without unauthorized paid API or external copyrighted uploads. Offline Piper is an experimental local TTS synthesizer, not an LLM and not approved as the formal voice. Source PDFs/media stay private. Future work should build genuinely new and source-grounded section physics QA, rather than rerun previous figure or superscript defects as separate one-off fixes.
