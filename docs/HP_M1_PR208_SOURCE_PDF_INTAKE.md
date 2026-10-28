# PR #208 — Original source.pdf-only preparation preflight

**Original** `tlyoon/MicroGen_AI`, on **HP only**, based on verified main merge `39c0bf094a17d1270a36a2272cb7bce97e4cac5a`. This tool is read-only for the original textbook source folder; it does not synthesize, generate slides/media, connect to Gemini, call Whisper, render lectures, merge code or publish materials.

## Problem and scope

Before this change, `microgen_pipeline_completion.production_contract` requires existing `slides.pdf` and `script_tts.json`, so an unattempted original textbook subchapter containing **only `source.pdf`** cannot be checked using the lecture-production contract. Starting a costly multimodal generation merely to discover an invalid, scanned, malformed or incompletely extracted source PDF is inefficient.

`microgen_source_pdf_intake.py` adds a bounded source-only first stage. It verifies exactly `source.pdf`, immutable SHA-256, PDF readability, page count, page dimensions, extracted text coverage and basic source figure references. It then invokes existing source-bound figure and equation geometry candidate scanners, saving three JSON receipts in a **new independent output directory**. The original folder is never modified. Missing or corrupt PDF, unsafe symlinks, reuse of output, source hash drift and invalid geometry fail closed. A scanned PDF produces an explicit `SOURCE_TEXT_EXTRACTION_REQUIRED` status instead of a false content-ready assertion. A technically readable source yields `PROCEED_TO_GROUNDED_SLIDES_AND_NARRATION`, **not** a generated lecture.

## Genuine HP pilot, 28 October 2026

| Source | Original pages | Searchable text | Figure candidates | Equation-line candidates |
|---|---:|---|---:|---:|
| Serway 1.1 | 4 | Ready | 2 | 0 |
| Serway 1.2 | 5 | Ready | 2 | 2 |
| Thomas 2.5 | 11 | Ready | 4 | 335 |

The original input SHA-256 was recomputed after running the pilot and matched all three receipts. A source-only geometry candidate is **not** academic correctness, and 335 Thomas equation-like lines include possible mixed prose or false positives. These counts must not be used to certify mathematics or figure meaning.

Independent HP receipts:
- `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_SOURCE_INTAKE_SERWAY_1_1\source_intake_receipt.json`
- `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_SOURCE_INTAKE_SERWAY_1_2\source_intake_receipt.json`
- `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_SOURCE_INTAKE_THOMAS_2_5\source_intake_receipt.json`

## Safety and remaining scientific acceptance

The generated receipt always sets `publication_allowed=false`, `generated_slides=false`, `generated_audio=false`, `generated_video=false`, `source_math_correctness_verified=false`, `figure_caption_semantics_verified=false` and `narrated_element_sync_verified=false`. This stage removes a source-ingestion bottleneck and demonstrates more than one textbook/section, **not** the full Serway video-generation lifecycle. Source figure/equation alignment, real mathematical content, phonetic correctness and element-level synchronized highlighting remain outstanding before lecture publication.

Tests cover original PDF integrity, searchable and scanned PDFs, malformed input, unsafe original/output locations, source hash change during geometry scanning, preservation of unrelated files, and symlink rejection where the Windows process has symlink privileges. No billed services or other PCs.
