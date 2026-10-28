# Scientific/figure review safeguards (Thomas Calculus QA, 2026-10-16)

MicroGen's verified completion receipt establishes **structural/media integrity**, not
proof of mathematical correctness or spoken scientific accuracy.

## Fail-closed title narration check
The manuscript title in `slides.tex` and the first narration object are
compared for a specifically recognizable truncation: if the speaker text is
a literal prefix of the title but omits the end, `check_narration` rejects the
bundle. This caught Thomas 8.5 title narration ending after "Partial" while
the slide said "Partial Fractions". Custom spoken introductions not matching
the title prefix remain allowed.

## Advisory figure-display check
`figure_display_warnings` inspects embedded raster image rectangles in the
actual rendered `slides.pdf`. Tall composite scientific figures presented as
less than 12% of slide width and less than 27% of slide height are flagged
for visual review, and the completion receipt is marked
`scientific_review_pending`. Do not silently crop/exclude source panels:
reflow the layout, split across slides, or reposition complete panels with
provenance recorded.

The Thomas 8.4 Figure 8.3 three-graph vertical composite was squeezed to
about 8% of slide width. A reviewed horizontal three-panel rearrangement
increased displayed width to about 80%, preserving all three curves and labels.
The layout change remained the same number of slides; the MP4 was reassembled
using the existing verified WAVs except for a separately corrected narration.

## Source math restrictions
The slide prompt explicitly prohibits inventing parameter restrictions beyond
the textbook. Formula 29b in Thomas 8.6 requires `b>0`, while `a` can be
negative when the expression is defined; incorrectly adding `a>0` is a
scientific defect. The narration prompt also warns that tangent is not
nonnegative on the entire arctangent principal interval. Signs, absolute
values and radical domains require source/math checks.

## Release criteria
- Verify the textbook origin of each named figure and all its subpanels.
- Distinguish a skipped **exercise-only diagram** from a missing lecture
  figure. Keep evidence of the source page and the reviewed scope.
- Differentiate or otherwise verify representative antiderivatives.
- Compare slide count with narration sidecar, WAVs and PDF slices.
- Check actual rendered slide readability at projected dimensions.
- Synchronize narration text, sidecar and regenerated WAV when an explanation
  is mathematically corrected. Reuse unchanged WAVs only with verified
  input-bound TTS cache and a consistent provider/voice.
- Use backup-and-rollback publication and verify the manifest after any edit.
- **2026-10-20 autonomous QA update:** human listening and lecturer review are
  optional audits, **not mandatory development or technical progression gates**.
  A successful automatic test does not imply human certification or full
  academic/figure/highlighting correctness. See
  `AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md` (authoritative).

The optional advisory cannot cover all mathematical mistakes, text-only
diagrams or visual issues, so users should not treat it as an academic
certificate.
