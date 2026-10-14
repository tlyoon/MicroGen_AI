# Composite-figure review gate

This release hardens source-derived figure publication. Figure mapping may produce a composite candidate and a hash-bound provenance receipt; that is **not** evidence that its panels were arranged, cropped, or captioned correctly. In particular, the current collector stitches multiple crops horizontally, which might not match the original textbook's vertical panel arrangement.

## What changes

- Figure extraction, mapping, draft slides, and technical tests may continue normally.
- Final verified publication now fails closed when `figure_composition_receipt.json` has any `review_required: true` entry without a matching `figure_review_approval.json` in the staging directory.
- Only a person who has checked the original source panels, sequence, axes, labels, equations, caption association, and output crop may create a review approval record. No LLM or automatic process should synthesize one.
- The approval is bound to each final figure SHA-256, originating source page, and panel count. Changed figure content invalidates it. The approval file is copied into the published bundle and its hash is retained in the completion marker.
- Ordinary one-crop figures that are not flagged as composites remain mechanically checkable, but **do not** become scientifically certified. If a single crop itself omits an original subpanel, automated checks might not detect it.
- The review record is an accountable workflow annotation, **not a cryptographic identity signature**. Appropriate folder access controls and an independent academic reviewer remain essential.

## Example review record

Save `figure_review_approval.json` next to `figure_composition_receipt.json` **only after visual review**:

```json
{
  "schema_version": 1,
  "reviewer": "Reviewer name or accountable identifier",
  "review_note": "Compared the output with original source page; complete and correct ordering, labels, caption and panels",
  "figures": [
    {
      "destination": "Figure 2.10.png",
      "output_sha256": "<copy exact output_sha256 from receipt after inspection>",
      "source_page": "page_3",
      "panel_count": 3,
      "approved": true
    }
  ]
}
```

If any flagged figure is absent, changed, mismatched, duplicated, or not expressly approved, `manifest_for` refuses completion. A figure with no review flag does not require the file.

## Testing and boundaries

Run `python -m unittest discover -s tests -p 'test_microgen_*.py' -q`.

This gate does not perform source-page semantic recognition, mathematical proof checking, narration listening, slide visual validation, or student publication authorization. An end-to-end campaign still needs the separate academic-review step. Preserve original textbook and production folders; review experimental outputs separately.

## Unmapped source-crop visibility

The 2026-10-15 live Section 8.6 pilot extracted an unnumbered gasoline-tank diagram accompanying Exercise 62. Its figure-composition receipt correctly contained no formally numbered mapped images, but did not expose the unused source crop to reviewers. That is a coverage-audit gap, not proof the generated lecture ought to teach Exercise 62.

The final technical completion manifest now contains `unmapped_source_crops` when extracted `crops/page_N/fig_*.png` files have no hash-matched mapped figure destination. Entries record the source page, crop filename, content SHA-256, and an explicit `review_required` flag. If any exist, `scientific_review_pending` is true. This preserves useful unattended technical generation, but prevents a human reviewer from mistaking a figure-free receipt for proof that the textbook contains no unmapped illustrations.

The audit **does not automatically decide** whether an exercise-only figure should appear in a lecture. There is no implicit academic approval. Technical validation still cannot certify source completeness, mathematical correctness, or authority to publish to students. Prior historical manifests without this field are not retroactively audited.
