# Original MicroGen_AI — HP Milestone 1, actual PDF-first offline extraction (26 October 2026)

**Owner current governing policy:** ORIGINAL `tlyoon/MicroGen_AI` development and local testing **HP only**. Dell-115 reserved for `MicroGen_AI_Web`; no HP/Yoga6/Zenbook crossover, protected historical G: output overwrite, main merge, public publication, extra paid API/TTS use, or Whisper. This PR is the smallest justified **fresh upstream source stage**, not another open-ended QA framework or a declaration of release readiness.

## Root problem and change

The earlier Milestone 1 verified a 552.75-second corrected lecture on HP, but only by reconstructing historical `slides.pdf`, existing narration and prerecorded WAVs. The original source PDF → new figures → new slides/TTS upstream process was unproven on HP. Worse, the batch runner's `figure_extraction` acceptance only checked whether `pages/page_*` *existed*; partial Docling runs could be treated as complete. A failed Docling conversion on any page previously merely printed an error and continued.

**New bounded capability:** `microgen_batch.py --figure-extraction-only` runs **only local, non-Gemini/Cloud Docling source page+figure extraction** and stops before `figure_mapping`, new slides, narration, TTS, video and publishing, without deleting the page/figure assets. Each completed page and extracted figure is recorded with original source SHA-256 and per-file SHA-256 in a new `figure_extraction_receipt.json`. `stage_valid` rechecks source page count, all source page PDF/PNG assets, hashes and figure inventory and rejects missing/incomplete/tampered receipts. Docling exceptions for any page now fail the run; no false success. A successful extraction saves the standard reusable `.microgen_checkpoint.json`, so a later authorized full run can resume with the same source files rather than needlessly repeating Docling. No output copied into protected source directories in the offline mode.

Only local PDF and Docling dependencies are checked for `--figure-extraction-only`; normal full-generation preflight remains unchanged. The option refuses multi-PC execution, with a clear report status `offline_figure_extraction_complete`, `gemini_or_tts_invoked=false`, `published=false`. It returns process exit 0 **only when extraction was actually complete**; this exit code does not imply full lecture/release completion.

## Real HP execution evidence — NO fake/generated test-only fixture

- Source: `G:\My Drive\Projects\Thomas_calculus_13ed\2\2.5\source.pdf`, original SHA-256 `dbc34b5de194c3eedcfc686dfabacc903cc45d858b7a5240912a358d2f2f384b`; historical G: files remain read-only and unmodified.
- Isolated fresh HP branch checkout `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_source_stage` stacked on HP-only #193, and fresh offline campaign `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY`.
- Source/figure operations used already-installed HP Conda interpreter `C:\Users\tlyoo\miniconda3\envs\docling_win\python.exe` (Docling, pdf2image), with main interpreter from prior isolated HP Milestone1 venv; did NOT request paid services. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` prevented model downloads. No Whisper or other-device actions.
- Executed actual `python microgen_batch.py --repo ... --source-root ... --work-root ... --targets 2.5 --main-py ... --docling-py ... --stage-retries 0 --fail-fast --source-wait 0 --figure-extraction-only`.
- **Real result: exit 0, all 11 original source PDF pages converted to one-page PDF and PNG assets, 20 Docling-extracted figure candidates**. Per-page extraction counts: `1,2,2,2,1,1,2,5,2,2,0`. Figure count does not establish correct labels, crops or source fidelity; those remain academic checks.
- Source-bound `2.5\figure_extraction_receipt.json` SHA-256 `039b011a32523e05fc24f4948abd27ef094d945e7bb104ea4b30a19f8c3da22e`. Source checkpoint `2.5\.microgen_checkpoint.json` marks ONLY `figure_extraction` complete, NOT figure mapping, generated slides/narration/TTS or publication. Batch report `batch_report.json`: `status=offline_figure_extraction_complete`, `source_pages_complete=true`, `gemini_or_tts_invoked=false`, `published=false`.
- Focused adversarial source-stage tests: **13/13 passed**, covering missing/tampered pages/receipts, changed original source, corrupted figures/false approvals, and paid-stage stop logic. Full HP regression result to be appended when verified.

## Exact owner-approved continuation

**Do not** claim full textbook-to-video M1 finished; the upstream `figure_mapping`, new LLM slides, new narration and TTS stages have not been executed on HP under an explicitly cost-approved provider arrangement. Current output demonstrates the first independent fresh textbook source step. Figure quantity does not imply 20 academically correct figures. Focus on source figure candidate QA and cost-aware next stage only; avoid increasing PR count without concrete completion evidence. Never automatically publish or mark mathematical/phonetic correctness passed.

## Final HP regression and genuine resumability evidence

- 13 new adversarial focused tests: **13/13 passed**.
- **Full HP `pytest tests -q`: 904 passed, 4 skipped, 1 benign warning; 101 subtests passed; exit 0**. Baseline from #193 was 891 passed, 4 skipped. No new project CI dependency or production billing needed.
- **Actual rerun of the same HP source-only batch** (the same source + stage + checkpoint), with cloud stages disabled: printed **`resume: figure_extraction and dependencies verified`** then **`OFFLINE_FIGURE_EXTRACTION_COMPLETE; paid stages NOT run`**, exit 0, without rerunning costly Docling extraction. This confirms the stage is reusable after handoff; it does not independently validate generated figure labels or semantics.
- Protected G: textbook source was read only. No Gemini/Google Cloud TTS calls, no publication, no modified historical media or protected main.

- Legacy HP `unittest discover -s tests -q` passed: **593 tests, 3 skipped, exit 0**. GitHub CI verifies platform regressions; none of these tests constitute mathematical figure or pronunciation signoff.
