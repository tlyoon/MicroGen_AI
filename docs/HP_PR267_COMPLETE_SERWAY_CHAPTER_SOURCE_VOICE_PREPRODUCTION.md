# PR267 — Complete Chapter 1 source/science and private narration handoff

## Goal and implementation

Advance original MicroGen_AI from repeated per-PDF corrections to one repeatable complete-chapter preproduction workflow. The new microgen_private_chapter_voice_campaign.py takes a private JSON manifest naming the chapter, an EXPLICIT ordered and contiguous expected section inventory, and original source PDFs, prior original authoring packets/drafts, accepted private source stages and corresponding rendered slide directories. Every expected section is mandatory.

The workflow SHA-freezes original PDF/packet/draft/source-stage/narration/plan/contract/figure/slide/receipt files. It reuses the existing strict source/science unified validator and the provider-neutral voice handoff verifier, checks all source/deck/page/topic/narration identities, creates one exact narration request per slide and an EMPTY source SHA-bound capture template for later authorized provider WAVs, and publishes all evidence atomically to ONE fresh PRIVATE output directory. A failed member rejects the entire chapter with no final partial receipt. No PDF, audio or video generation, cloud provider, local LLM or paid API is invoked.

The chapter report contains ONLY IDs/hashes/counts and explicit status flags; per-section PRIVATE voice input bundles contain the original authored narration and must not be committed, publicized, or sent to unapproved providers. Formal voice approval, copyright rights, publisher-outline completeness, general academic semantic completeness and publication authorization all remain FALSE.

## Prevent stale source segmentation from blocking the chapter

The older Section 1.1 source packet had 20 original bounded passages; the current source PDF extractor finds 30 passages from the SAME immutable source PDF. New microgen_private_source_citation_relink.py independently verifies both the old packet and original source-bound author draft, requires a UNIQUE original citation anchor on the SAME original source page for each topic, and re-links only passage IDs and the packet SHA. It verifies old and newly relinked source citations with the established source/numeric/anti-copy gate. Original authored narration, slide titles and bullets are never edited. A source or citation drift with no unique anchor remains rejected, never bypassed.

In the real Section 1.1 demonstration all 11 old authored topics were safely relinked and revalidated against 30 original PDF passages. The existing two independently source-verified original figure PNGs were SHA-preserved, attached to the NEW private stage, and rechecked for exact original PDF pixel/caption provenance. The updated 11-slide deck and original source-scientific QA passed.

## Close a genuine compiled-stage provenance blind spot

The prior atomic source/science validator independently approved model draft and compiled stage but did not require their actual text to match. One adversarial synthetic test showed a source-valid edited draft could be paired with an unchanged compiled deck when the section topic count matched. The enhanced microgen_private_unified_campaign.py now requires EVERY original author title, bullet array, narration, term inventory, topic ID and source page to be IDENTICAL in the compiled stage.

Older Section 1.2 retains a historical packet/draft SHA metadata discrepancy, but ALL 16 actual authored slide contents are identical to the compiled lecture. Preserve that content and report ONE legacy SHA lineage advisory, rather than forge a strict historical SHA identity or regenerate an unchanged lecture. All other five sections have strict current lineage.

## Real Serway Chapter 1, Sections 1.1 through 1.6

- Six original, source/science-validated teaching sections
- 57 total rendered teaching slides and 57 exact future voice requests
- 137 independently recovered original source passage blocks, 90 directly cited
- All source PDFs unchanged; old source figures retained and pixel-verified
- All 57 compiled authored texts match their source-approved original drafts
- Exactly one legacy authoring SHA lineage advisory (Section 1.2)
- Zero TTS synthesis jobs, paid provider calls or local language-model invocations
- NOT six formal audio/video lectures, NOT publication approved

PRIVATE source/draft/stage and new chapter manifest:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR267_SERWAY1_SIX_SECTION_CURRENT_SOURCE_MANIFEST_PRIVATE.json

PRIVATE final successful chapter receipts, 57 exact narration requests and blank capture templates:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR267_SERWAY1_SIX_SECTION_REAUDITED_VOICE_PRIVATE

PRIVATE reusable Section 1.1 source migration:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR267_SERWAY11_REUSABLE_CITATION_RELINK_PRIVATE

PRIVATE pixel-checked Section 1.1 rendered slide deck:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR267_SERWAY11_RELINKED_SOURCE_FIGURES_SLIDES

## Tests, device and continuation contract

Synthetic tests cover complete chapter evidence and two-section voice requests, tampered source/draft/deck/voice, missing/reordered sections, unsafe output paths and atomic failure. Citation-migration synthetic tests cover old passage-ID versions, unchanged narrated content, forged source/page/anchor, and safe fresh packet output. Unified audit test checks that a source-valid draft differing from compiled content is rejected. No private textbook, voice, figure or scripts are committed to public GitHub.

Only authorized HP desktop for original MicroGen_AI code and technical QA; original prose by ChatGPT/Gemini only. NEVER install or use a local language model or unapproved paid provider API. Existing optional Piper is experimental offline TTS, not the formal approved voice. Require complete HP pytest pass, and all FOUR GitHub Windows/Ubuntu Python 3.11/3.12 jobs PASS on exact PR head before squash merge and safe HP sync. The immediate remaining dependency for genuinely finished publishable lectures is authorized formal TTS acquisition, independent acoustic checks and copyright/publication signoff, not repeated textbook PDF patching.
