# PR #212 — Genuine offline original-PDF figure mapping without a provider call

Project: original **tlyoon/MicroGen_AI**, HP only, following merged main `33f561d78d7794cf49be5f1b1c62cd144c852897`. This improvement does NOT change the original generation model, TTS voice or publication contract, and does not substitute an unrelated media provider.

## Actual change

The original batch treats `figure_mapping` as an obligatory Gemini stage. This PR introduces an *opt-in, narrowly supported* no-network path:

```powershell
python microgen_batch.py --source-root "G:\My Drive\Serway\Serway_1_7" --targets 1.1 --work-root "C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR212_REAL_BOUNDED_OFFLINE_RUN" --offline-figure-mapping --stop-after figure_merge --main-py "C:\Users\tlyoo\miniforge3\envs\microgen_ai\python.exe" --docling-py "C:\Users\tlyoo\miniforge3\envs\microgen_ai\python.exe"
```

The new local mapper `microgen_offline_pdf_figure_map.py` requires:
- complete original-PDF Docling extraction/verified per-page image SHA evidence;
- exactly **one** formal captioned, two-image/two-crop page, no other unmatched embedded source images or crops;
- two **geometrically bound panel letters a and b** directly beneath the respective original PDF images, plus a formal `Figure N.M` caption which explicitly mentions both panels;
- **unique and strong image-feature correspondence**, each crop with at least 35 good ORB matches and ≥4× best-to-second-best score separation, assigning exactly one original embedded image to each source crop;
- no preexisting output figure or mapping receipt, source PDF SHA immutability and the existing collision-safe source-crop composition receipt.

It outputs an exact source-linked two-panel composite and calls the existing `validate_figure_receipt` before the original local `figure_merge` stage. It does **not** issue Gemini requests or claim equivalence of depicted scientific concepts. If any rule cannot be proven, it rejects the page and leaves paid stages uninvoked. Other figure layouts remain unsupported by this offline mode; the default generator still has its original provider pathway.

`--offline-figure-mapping` is explicitly restricted to `--stop-after figure_mapping` or `--stop-after figure_merge`, and rejects `--authorize-provider-usage`, multipart, multi-PC and extraction-only conflicts. It never authorizes slides, narration, TTS, video or publishing. Normal generation behavior is preserved when the flag is omitted.

## Real original Serway §1.1 HP pilot

Protected source: `G:\My Drive\Serway\Serway_1_7\1\1.1\source.pdf`, 4 pages, original SHA-256 `a9727afee30282deeb22f34ce67323e168ab6a2893f2754f27f683ab28b9` unchanged.

- Genuine source PDF page 2: image 1 xref 72 and image 2 xref 73, labelled **a** and **b** beneath the respective images, followed by formal `Figure 1.1` caption.
- Real Docling `fig_1.png` vs original embedded image 1 yielded **257** good ORB matches vs image 2 **5**. Real `fig_2.png` vs image 2 yielded **396** vs image 1 **4**. Cross-assignments are unambiguous.
- A genuine fresh isolated full `microgen_batch.py` run (not a mocked unit test) executed `figure_extraction`, `figure_mapping` and `figure_merge` without provider authorization, completed in **61.92 s**, exit 0, status `bounded_stage_complete`.
- The actual composite `Figure 1.1.png` contains the two ordered original-source panel crops; SHA-256 `cf4a46a680648d1908f6703ca040fa36a6be94511e36cea841a43ca1f1803179`. `figure_composition_receipt.json` records both source crops, panel counts and figure provenance. `review_required=true` for the two-panel figure and `publication_allowed=false` in the new mapping receipt.
- An immediate second full batch invocation on the *same* scratch safely resumed all three original stages with their verified dependency fingerprints and stopped at the same boundary without re-extraction or paid calls.
- Real HP scratch is `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261029_HP_PR212_REAL_BOUNDED_OFFLINE_RUN\1.1` and contains `offline_figure_mapping_receipt.json`, `figure_composition_receipt.json`, `Figure 1.1.png` and `.microgen_checkpoint.json`. The original source Drive folder is unchanged.

## Scientific and release limitations

This proves source image/caption association for one unusually well-grounded two-panel figure, **not** automatic academic proof for arbitrary scientific images. No new lecture slides, narration, WAVs or MP4 are produced in this offline campaign. Subsequent `slides`, `narration` and `tts` in the original package remain provider-dependent; they must not be represented as completed or silently billed. No upload to YouTube or Moodle, and no manual academic approval is claimed.

Offline only, no token cost, no Whisper, no access to Dell-115, Yoga6 or Zenbook.
