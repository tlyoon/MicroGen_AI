# PR245 — Verified original source-PDF figure crops and adjacent caption evidence

The existing portable renderer checked that a figure image file had the correct SHA and was embedded unchanged into the PDF slide. That proves **internal asset identity**, but does not establish that the figure came from the intended **source PDF region**. This milestone closes that provenance gap for figure rows supplying explicit source-page/geometry/caption fields.

## Source-figure evidence contract (optional to preserve existing workflows)

Existing manifest `figures` rows can additionally supply all of:

```json
{
  "source_figure_page": 4,
  "source_figure_bbox": [449, 58, 580, 260],
  "source_figure_label": "Figure 1.3",
  "source_pixel_sha256": "sha256_of_original_source_raster_RGB_samples"
}
```

The PDF source crop must contain the entire specified rectangle, the original source must be present and SHA-bound by the existing section contract, and the PNG source image must match the source PDF raster **exactly byte-for-byte at its original pixel size**. The derived `source_pixel_sha256` is computed from the raw RGB raster samples, independent of PNG metadata. The exact figure label must appear in the same original source page in a proximity window below the candidate crop (the window does not imply caption-semantic correctness).

The new `microgen_portable_source_figure_regions.py` rejects partial declarations, incorrect source page, invalid or shifted bbox, mismatched or mutated images, untrustworthy PNG proportions, absent nearby captions, nonlossless image files and raster SHA mismatch. It **does not** accept matching image SHA alone as source-origin proof. Old image-only manifests continue to render but report zero verified source-PDF figure regions; no false blanket provenance approval is asserted.

`microgen_portable_slide_render.py` places the independent geometry/caption receipt alongside each slide's original figure hash, and summarizes how many mapped figures have stronger verification. `microgen_portable_lecture_pipeline.py` passes this evidence summary to its end-to-end media receipt.

## Actual authorized HP real-source validation

Original private Serway **Section 1.2 Modeling and Alternative Representations** five-page PDF SHA `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb` unchanged.

Four actual original figure panels reproduced at exact pixels and nearby exact source caption markers: Figure 1.2 (tree), Figure 1.3 (baseball illustration), Figure 1.4 (simplified velocity diagram), Figure 1.5 (oscillating position-time graph). A fresh immutable private source manifest with all four original PDF page/bbox/pixel SHA/label declarations is in `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR245_SERWAY12_ALL_FIGURES_SOURCE_GEOMETRY_STAGE`. Independent fresh **16-page PDF**, verified **4/4 original PDF crop and nearby caption evidence**, SHA `8b50ac0dd2a0f445d1a58252d49f9f379e9593ebe5af3e13d1b205f1e1aebe60` in `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR245_SERWAY12_FOUR_FIGURE_SOURCE_VERIFIED_PDF`.

Private receipt: `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR245_REAL_SERWAY12_FIGURE_PROVENANCE_QA.json`. The original PR243 lecture media is immutable and retained; any new end-to-end video is in a separately versioned private folder.

## Verification and limitations

Wholly synthetic `tests/test_microgen_portable_source_figure_regions.py` covers positive source-PDF raster proof and negative page, source caption, crop, partial keys, pixel hash, edited PNG and wrong aspect ratio. Historical portable image-only pipeline remains compatible. The checks verify physical file/page/caption proximity and pixel identity, **not** full mathematical correctness, whether an image conceptually matches the narration, textbook figure distribution rights or a formal production narrator. All `publication_allowed=false`.

Next priority: independent mathematical relation/dimension and semantically source-grounded figure/text reasoning, plus research/validation of genuinely automatic original lesson writing, with conservative claims and no brittle audio recognition hard gate.
