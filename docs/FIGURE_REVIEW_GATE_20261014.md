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
