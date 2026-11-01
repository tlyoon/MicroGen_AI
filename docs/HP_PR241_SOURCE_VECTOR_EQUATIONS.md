# HP PR241 — Original-PDF vector equation regions (private candidate only)

## Motivation and scope

The PR240 portable slide renderer intentionally rejected Unicode or LaTeX mathematical notation instead of showing corrupted symbols. This increment adds **source-preserving vector-equation excerpts** to the portable renderer. It does **not** yet typeset new arbitrary LaTeX equations or prove their academic correctness. Visible slide bullets remain restricted to safe ASCII.

An optional `source_equations` list in the portable section manifest has one mapping per slide, each containing:

- `slide`: 1-based target slide, whose declared original source page must match;
- `source_page`: 1-based page of the exact SHA-bound `source.pdf`;
- `source_bbox`: four original PDF-point coordinates enclosing the original mathematical expression;
- `source_crop_sha256`: SHA-256 of the 2x sRGB source crop with width/height included, produced by `microgen_portable_source_equations.crop_sha`.

The renderer uses PyMuPDF `show_pdf_page` to embed the original source's PDF vector content, rather than substituting ASCII letters or guessing font glyphs. It verifies source-crop SHA, geometrical containment, source page identity, presence of visible ink, page boundary, source hash immutability, and a vector XObject in the rendered slide. It forbids equation and mapped figure on the same slide until an independently checked nonoverlapping layout exists, and permits at most three bullets on an equation slide.

First-page equation crops must begin *below* a searchable original start marker, preventing accidental borrowing from the preceding section. Equation crops on the last page of a PDF with a next-section marker are conservatively rejected to avoid subsequent-section contamination. This overrejects some legitimate last-page equations and is intentionally a safety restriction rather than silent proof.

## Actual HP second-source evidence

Read-only Serway 1.2 original: `G:\My Drive\Serway\Serway_1_7\1\1.2\source.pdf`. Source SHA `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`, five pages, section 1.3 begins on page five. The original mathematical region on page two `[106,681,312,724]` was copied into a separate **private** candidate PDF with preserved vector XObject and verified stable hash. Output and JSON receipt are under `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR241_REAL_SERWAY12_VECTOR_PROOF`. Original textbook source SHA unchanged. This is a *proof of provenance-preserving graphics*, not an audited full Section 1.2 lecture and not approval of the crop's scientific interpretation.

## Release / QA

- No external APIs, new paid provider calls, original media replacement, or Drive writes.
- Neither the source crop nor the synthesized slide receives mathematical-semantic approval merely because pixels and vector source match.
- `formal_voice_authorized=false` and `publication_allowed=false` remain enforced.
- Synthetic regression checks exercise vector survival, source-region SHA tampering, adjacent-section boundary, previous-section borrowing, and figure collision.
- Next milestones: independent figure/panel semantics for Section 1.2, mathematically authored source-grounded complete slide and narration manifest, full distinct real-source video; general mathematical typesetter as a separate bounded implementation when necessary.
