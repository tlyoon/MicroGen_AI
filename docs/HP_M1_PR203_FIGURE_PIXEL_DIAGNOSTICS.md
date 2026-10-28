# HP-only original textbook figure-pixel anomaly diagnostics — 28 October 2026

Stacked after original MicroGen_AI draft PR #202. All operations on HP in separate AppData checkout. Do not access other PCs, overwrite G: sources, synthesize speech, or publish.

## New reusable mechanism

`microgen_source_figure_pixel_match.py` re-opens the **exact source.pdf** and validates its SHA against the source-grounded PR #200 figure review receipt. Every image file is checked against both the immutable source-stage file SHA and matching review figure SHA. Source PDF pages are independently rasterized with PyMuPDF at fixed 1.4 scale, then the candidate crop is compared to its asserted source page with bounded multi-scale OpenCV normalized template matching.

All results are checksum-bound by the original source receipt. Suspect low-score cases (<0.65) are flagged as **diagnostic review required**. A high score **never** proves mathematical figure semantics, exact figure-to-narration timing, textbook fidelity of all labels, or permission to publish. This check does not silently replace or alter any mapped image.

## Genuine Section 2.5 pilot

Actual original Thomas Calculus 13th edition Section 2.5 source: 15 source-mapped images / 15 Beamer image references on 11 source pages. The real-pilot result in `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261028_HP_M1_FIGURE_PIXEL_PROVENANCE\pixel_comparison_receipt.json` reports 15 checked and **0 low-match flags**. An earlier exploratory screen-image check found correlations 0.7756 to 0.9429; those are approximate pixel correlations, not semantic approval. All sources and prior MP4/WAV/slide assets remain untouched.

Five focused tests cover correctly localized source crop, wrong crop, blank input, illegal scale and no valid scale. OpenCV and NumPy are optional runtime dependencies for this diagnostic; hosted minimal environments without them will skip these tests, not claim QA verification. HP has both.

## Remaining blockers

The pixel check reduces the chance of mis-assigned page/figure crops but cannot certify figure mathematical meaning, audio pronunciation, element-level highlighting or overall academic correctness. Publication remains explicitly blocked; retain the original source and prior review packets. Do not merge the pending stacked PRs without integration review.
