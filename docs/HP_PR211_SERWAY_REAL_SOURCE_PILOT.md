# PR #211 — Genuine Serway 1.1 source-run and honest provider-boundary QA

**Original tlyoon/MicroGen_AI**, HP only. This is a second **original-source pilot**, not a fictitious second complete lecture. The current source-to-video producer uses Gemini API for mapping, slides and narration and Google Cloud TTS for audio; those calls are not authorized under the present no-paid-API execution restriction. All test code is local and no customer Google Drive textbook file is modified.

## Genuine HP campaign

Original unmodified input: `G:\My Drive\Serway\Serway_1_7\1\1.1\source.pdf`, **4 pages**, source SHA-256 `a9727afee30282deeb22f34ce67323e168ab6a2893f2754f27f683ab28b9`.

Original batch runner invoked in `--figure-extraction-only` mode in the HP scratch directory `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR211_SERWAY_1_1_OFFLINE_CAMPAIGN`. Existing current MicroGen_AI code genuinely processed all four original pages through Docling (CPU) in **80.84 seconds**, retained **2 figure crops on page 2**, emitted `figure_extraction_receipt.json`, full per-page PNG/PDF hash evidence, and `batch_report.json` recording `offline_figure_extraction_complete`. Docling, PDF reader and local scratch checks passed, extraction exited 0. Original and scratch source SHA were independently equal. No generated slides, narration, WAV, MP4, or paid provider call.

This first pilot was initially invoked without an explicit `--commit`, resulting in an honest checkpoint field `package_commit=unknown`. This must not be represented as pinned code provenance. For reproducibility, a separate pristine original-main campaign with explicit full 40-character `--commit 01c36e1c90cec765eecfe2c460d1aa44d2bb464d` is also being run; retain only the outcome that its actual report confirms, not hypothetical success.

## New fail-closed reusable proof

`microgen_second_source_acceptance.py` independently checks the **protected original PDF** against the scratch source copy and the Docling figure extraction receipt, every page and figure SHA through the package's real `source_page_extraction_valid`, existing completion timestamp and source-signature size, and a separate source-PDF geometry and text read via the already merged `microgen_source_pdf_intake`. It creates a **new external QA folder** containing a three-file source-intake evidence packet and an immutable `source_campaign_readiness.json`. Running it again against identical inputs is idempotent, and altered source, extraction receipt, checkpoint, page PNG/PDF or geometries reject acceptance. An explicitly supplied expected code commit must match the original checkpoint.

The report explicitly records `next_stage=figure_mapping`, `next_stage_uses_gemini=true`, `slides_and_narration_use_gemini=true`, `tts_requires_cloud_provider=true`, `provider_authorized_by_this_report=false`, `generated_slides=false`, `generated_wavs=false`, `generated_mp4s=false`, `second_end_to_end_generation_passed=false`, `publication_allowed=false`. Original files untouched; none of this is scientific lecture, audio pronunciation or full multimedia approval. Source-intake candidates are rough geometry—not validated figure semantics.

## Remaining work for actual second courseware

The **next provider-dependent stage** is `figure_mapping`. Then come source-grounded slide generation, narration and a voice-consistent TTS, video splitting when approaching 600s, synchronized equation/figure highlighting and independent academic/acoustic release checks. The package must not call billable providers without explicit authorization, nor silently switch to a different TTS voice to create misleading 'completed' evidence. Existing original Thomas §2.5 is a separate genuine rendered media case; the new Serway 1.1 evidence proves only a **fully executed and recoverable offline source-extraction stage**, not an end-to-end second video.

## Execution mode and reproducibility

HP only, no Dell-115/Yoga 6/Zenbook, no Whisper. Use `python microgen_batch.py --figure-extraction-only` first and follow with:

```powershell
python microgen_second_source_acceptance.py --source-pdf "G:\My Drive\Serway\Serway_1_7\1\1.1\source.pdf" --stage "C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR211_SERWAY_1_1_OFFLINE_CAMPAIGN\1.1" --new-report-directory "C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR211_SERWAY_1_1_SOURCE_QA"
```

The report is source-only and deliberately does not issue, infer or silently grant provider authorization or publication permission.


## Completed pinned verification (29 October 2026)

A **separate second full Docling extraction** was run from the previous merged `main` HEAD `01c36e1c90cec765eecfe2c460d1aa44d2bb464d`, with `--commit` explicitly pinned, from the source original. This is a different scratch root: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR211_SERWAY_1_1_PINNED_CAMPAIGN`. The entire offline stage completed successfully in **32.55 seconds**, exit 0, again finding **four pages and two extracted figure crops**. No billable provider stage ran. Original source hash was rechecked identical: `a9727afee30282deeb22f34ce67323e168ab6a2893f2754f27f683ab28b9`.

The independent `microgen_second_source_acceptance.py` was run twice with `--expected-commit` matching the frozen full Git SHA against this pinned campaign. Both calls returned:

```json
{
  "status": "SOURCE_ONLY_STAGE_COMPLETE_PROVIDER_DEPENDENT_STAGES_PENDING",
  "source_pages": 4,
  "docling_extracted_figures": 2,
  "source_geometry_figure_candidates": 2,
  "next_stage": "figure_mapping",
  "second_end_to_end_generation_passed": false,
  "publication_allowed": false
}
```

The detailed source-bound proof is `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR211_SERWAY_1_1_PINNED_SOURCE_QA\source_campaign_readiness.json`. It sets `code_commit_pinned=true` and stores the explicit commit, the Docling extraction SHA, independent intake geometry/equation evidence and immutable source SHA. The independent extraction finds **zero equation-like source lines** in this section, which is a geometry heuristic, not an academic assessment.

The first run (without `--commit`) remains an honestly **un-pinned** record; its receipt must not be silently rewritten into the second pinned outcome. The two campaigns are independent.
