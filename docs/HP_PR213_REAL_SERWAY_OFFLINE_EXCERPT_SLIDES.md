# PR #213 — Real source-bound offline slide **draft**, not completed lecture

Original `tlyoon/MicroGen_AI` on **HP only**, based on merged `main` commit `329beace16e9f8ba226e3c32e94cb9c941ba5bab`. Never call Gemini, TTS, Whisper or API; never change the agreed narrator voice; preserve all protected textbook and current production assets.

## Actual improvement

Adds `microgen_offline_source_slide_draft.py`, a narrowly defined **optional** first offline slide-drafting route for genuine original Serway Section 1.1. It builds a separate 8-page 16:9 PDF from 8 exact source-verbatim excerpts taken from the 4-page original PDF, and the existing two-panel `Figure 1.1.png` whose crop-to-embedded-PDF provenance was already verified in PR #212. It does not accept a model-generated unsourced explanation, an unverified figure, a missing original page, or overwritten output. Each source excerpt is checked against text extracted from its exact original PDF page; all source/figure identities are SHA-256 checked before and after. The resulting PDF page count, geometry, visible headings and SI-correction presence are independently rechecked.

**Critical academic currency correction:** the source textbook describes the kilogram prototype as defining the SI mass unit. This is historical, **not current**: the 26th CGPM Resolution 1 established the modern constant-defined SI effective 20 May 2019. Slide 4 clearly identifies the textbook prototype wording as historical and separately flags the newer Planck-constant definition with an embedded clickable primary BIPM URL: `https://www.bipm.org/en/committees/cg/cgpm/26-2018/resolution-1`. The external SI statement is **not** presented as an excerpt from the source PDF.

### Verified real HP source inputs and outputs

- Original Serway 1.1 `source.pdf` (4 pages): `G:\My Drive\Serway\Serway_1_7\1\1.1\source.pdf`; SHA-256 `a9727afee30282deeb22f34ce67323e168ab6a2893f2754f27f683ab28b9`.
- Already pinned PR #212 source/figure stage: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR212_PINNED_FIGURE_MAP_CAMPAIGN\1.1` with two-panel `Figure 1.1.png` source composition and academic-review flag still pending.
- Newly rendered **real draft**: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR213_SERWAY_1_1_EXCERPT_SLIDES_V2\slides_source_draft.pdf` (8 widescreen pages) and `slide_draft_receipt.json` with SHA-256 source, image, rendered PDF and all source excerpt references.
- The draft can be independently rendered, visually inspected and its metadata validated; it intentionally does not create the production `slides.pdf`, a narration `script_tts.json`, WAV, or MP4, and cannot serve as proof of full coverage, mathematical correctness, voice or element-sync quality.
- A visible source figure slide and the source-historical/current-SI distinction were inspected on the actual rendered PDF. The rendered page footers explicitly warn **NOT APPROVED FOR PUBLICATION**.
- Test coverage includes real PDF rendering from synthetic 4-page sources, source excerpt mismatch fail-closed, existing output preservation, separate output folder enforcement, actual figure embedded in PDF, BIPM URI on slide 4, all slide titles and count/16:9 dimensions. No API or network access is needed at runtime.

## Remaining honest dependency

This does not solve the same-voice TTS requirement. The current original project uses Gemini API for production slides and narration and Google Cloud TTS `en-US-Chirp-HD-F` by default for speech. HP has Chrome/Edge/Selenium and local ML packages, but no **verified free provider supplying the same voice**, so neither a browser-UI substitution nor an offline OS voice can be silently treated as identical. Final Serway Section 1.1 remains incomplete until source-grounded narration, matching TTS, full equation/figure sync, split videos under 600 s, academic/phonetic QA and safe publication acceptance are demonstrated.

The source-to-draft PDF route is a meaningful offline prototype, not the production LLM pipeline or a general-purpose textbook summarizer. Use source-specific narrative extrapolation only when separately source-verified and released under the correct project contract.
