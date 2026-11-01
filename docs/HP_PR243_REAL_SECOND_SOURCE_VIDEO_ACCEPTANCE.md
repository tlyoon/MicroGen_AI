# PR243 — Real second-textbook-subsection portable source-to-video acceptance

## Purpose

Prove that the original MicroGen_AI portable pipeline works on a **different actual textbook subsection**, not merely Serway 1.1 or the PR240 synthetic B.2 fixture. All copyrighted input and generated media remain private on the authorized HP computer. No protected media or narrator model weights are committed to GitHub.

## Original real source and section boundaries

- Real Cengage Serway physics **Section 1.2, Modeling and Alternative Representations**, private original `G:\My Drive\Serway\Serway_1_7\1\1.2\source.pdf`.
- Original immutable PDF: five physical pages, SHA-256 `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`.
- First PDF page begins with leftover Section 1.1. The PR242 source auditor excludes text before the 1.2 heading. The final PDF page begins Section 1.3 and is excluded from Section 1.2 source anchors.
- Private source input, source-to-slide manifest, narration and original image regions: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR243_SERWAY12_REAL_16_SOURCE_INPUT`.
- **16 independently named topic contracts** anchored to real original source pages and explicit spoken and displayed terms. Each slide has an original 96–109-word narration, original source-linked title and three bullets. Four original PDF image-panel crops are used for textbook Figures 1.2, 1.3, 1.4 and 1.5. PDF vector math uses the source-original tangent equation; `50 tan(25 degrees) = 23.31538 m` was separately computed.
- All 16 declared-topic checks pass. The claim is **declared topic coverage**, not independent proof that absolutely every pedagogical concept or scientific statement was audited.

## Actual end-to-end generated media

Command: existing `microgen_portable_lecture_pipeline.py`, original five-page source and authoring manifest, local offline Piper candidate voice, offline Vosk and local FFmpeg, transactional staging. **No Cloud/Gemini/provider charge**.

Private output, not uploaded: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR243_SERWAY12_REAL_16_FULL_OFFLINE_VIDEO_V1`.

- Fresh 16-page PDF SHA-256: `a2c6a413a25a5547fcd49b67312e7205eb30700481d0b98ee50aecf6dd68f169`.
- 16 real SHA-bound offline mono PCM16 WAV files totaling **625.208 s**.
- Actual playable H.264/AAC MP4 **627.981 s**, SHA-256 `db0d6958bc6b469dfb6673fdb65cc38904ee61d0000e40b1b8633cf7869b9bb0`.
- Pipeline's actual 16/16 decoded midpoint-to-PDF frame checks passed; every error fraction below 0.006.
- Additional **separate independent** read-only HP decoder reopened the final MP4 and compared all 16 newly decoded midpoints with the actual 16 rendered PDF slides: 16/16 passed, maximum normalized RGB mean error `0.005858`; FFprobe independently confirmed H.264/AAC and duration `627.981 s`.
- Offline ASR glossary advisory: **zero targeted contextual C-dot/Y-dot triggers**, **zero expected-term misses**. These are not full phoneme verification.
- Final postflight receipt saved privately as `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261101_HP_PR243_REAL_SERWAY12_INDEPENDENT_POSTFLIGHT.json`.
- Original source hash reverified unchanged; figure source crops, manifests and original WAV provenance remain versioned and separate.

## Reusable synthetic CI regression

`tests/test_microgen_portable_16_slide_source_figures.py` builds a *wholly synthetic* section with a 16-topic manifest, source equation, and four unique original image mappings. It verifies source-to-visible/voice contract alignment, original figure pixel identity, source PDF vector equation embedding, output page count and source immutability. It deliberately contains **no copyrighted textbook data**, no actual paid provider or model usage, no publication approval.

Focused legacy + new portable tests: **15 passed**. The whole HP root regression and all four hosted GitHub Actions Windows/Ubuntu Python 3.11/3.12 jobs must be checked on the exact PR head before merge.

## Explicit remaining limits

- The Piper voice is a local technical candidate, not the user's formally authorized production/default voice. Google Cloud remains allowed only for bounded isolated troubleshooting under the established contract.
- Source figure/crop and mathematical equation pixel fidelity does not certify every scientific claim, all oral pronunciations, accessibility or pedagogical completeness. A small ASR mismatch is advisory, not a blocker.
- The original textbook images and narrator model may have unresolved distribution rights. **No publication, release, Google Drive sync, or formal voice approval.**
- Future work: independent source-grounded semantic scientific QA at scale, comprehensive phonetic/listening verification without perpetual false-positive loops, production narrator/provider and distribution/license gate, then repeated real-world section batches and release acceptance.
