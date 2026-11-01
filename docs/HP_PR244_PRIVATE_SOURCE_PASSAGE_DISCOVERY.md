# PR244 — source-bounded automatic passage and candidate-topic discovery

## What changed

Introduces `microgen_source_passage_discovery.py`, a deterministic, private-first chapter-independent PDF pre-authoring tool. It finds text blocks inside an explicitly supplied section start and next-section boundary (or an explicitly declared end-of-PDF). It extracts SHA-locked source passages with page and PDF bounding boxes, original-page figure-number mentions, and **candidate authoring topics**. It optionally compares source-anchor overlaps against a previously authored source contract. Each passage/title is original **source text**, NOT a free-to-publish authored teaching slide or generated narration. The tool cannot certify that each passage is a unique learning objective.

Technical safeguards: source SHA before/after, distinct first-page preceding-section and last-page adjacent-section removal, conservative heading selection when running headers repeat, source-geometry crop bounds, precise copyright/footer detection (instead of fixed margin), short worked-example headings preserved, source-caption references rather than assumed figure-panel identity, no write into My Drive, no overwriting prior reports. Output statuses `publication_allowed=false`, `formal_voice_authorized=false`, `source_topic_completeness_proven=false`.

## Usage (PRIVATE and original textbook assets remain on the authorized HP)

```text
python microgen_source_passage_discovery.py --source <private-stage>/source.pdf --start-marker "Modeling and Alternative Representations" --next-marker "Dimensional Analysis" --contract <private-stage>/contract.json --new-private-report <fresh-private-file>.json
```

The contract is optional: without one the tool still inventories geometrically bounded PDF text; with one it verifies original source SHA, matching boundaries and nonpublication, and reports literal anchor overlaps for comparison. **Anchor overlap is advisory and does not establish semantic coverage**, even when every declared topic has a hit. A source page containing a scanned image with no readable text is not discovered as a passage. A successful report is therefore a reproducible *inventory for subsequent automated original authoring*, not a finished lecture.

## Verified real-source checkpoint (private, not in GitHub)

Original independent **actual Serway §1.2** source SHA-256 `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`. Fresh private report `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR244_REAL_SERWAY12_SOURCE_PASSAGES_V2_PRIVATE.json`:

- 34 source-evidence passages: page distribution 3/12/7/12/0.
- Found all source-referenced figure labels **Figure 1.2, 1.3, 1.4, 1.5** without asserting crop/caption semantic equivalence.
- Source-evidence overlap for **16/16 prior authored lecture topics**; 18 distinct passages have no matching declared-topic anchor, **not** proof of 18 missed concepts.
- Crucially, the final Mathematical representation paragraph on original physical page four is retained after switching to copyright-aware footer geometry; the last original page consists only of subsequent §1.3 and contributes zero passages.
- Original 5-page PDF unchanged; no model calls, paid cloud provider calls, protected-Drive changes, or release authorization.

All tests in `tests/test_microgen_source_passage_discovery.py` use synthetic PDFs: same-page and cross-page boundaries, repeated headers, first-page predecessor and last-page next-section quarantine, candidate title vs narration policy, footer-near-last-body paragraph retention, absent/reversed heading fail-closed, stale SHA, report overwrite refusal and source immutability.

## Next milestone

Connect source-inventory evidence to a **sound source-to-lecture authoring workflow** with independently original narration and a mathematics/figure semantic consistency check. Do not generate rote narration by copying copyrighted source paragraphs or conflate lexical overlap with scientific completeness. Continue the HP-only authorization, CI matrix and nonpublication/voice restrictions.
