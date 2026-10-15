# Publishing figures safely when Windows filename case differs

## Failure observed in the 15 October 2026 three-PC pilot

HP generated Thomas' Calculus Section 8.4 successfully, including the 18-slide
PDF, WAVs, and final MP4. Its last publication stage failed with a
`FileNotFoundError` while promoting a temporary figure candidate.

The generated LaTeX referred to `FIGURE 8.2.png`, while the actual image was
`Figure 8.2.png`. Windows resolves both spellings to the same file. The old
manifest recorded both names as distinct keys, however. During publication,
the two candidate paths referred to the *same* file on Windows; promoting
the first one consumed the temporary candidate, and the second promotion
then failed. Five figures were affected.

## Permanent correction

- Resolve every referenced figure to its real on-disk filename before
  collecting hashes. Multiple equivalent references produce one manifest
  entry and one destination-local promotion.
- Reject separate figure files whose names collide after Unicode
  `casefold()`, rather than allowing ambiguous cross-platform artifacts.
- Reject externally supplied manifests containing case-insensitive duplicate
  figure keys. Fail the published-manifest check on legacy ambiguous records
  so they are not silently trusted.
- For a genuinely vanished source candidate, re-stage **once only** from a
  file whose SHA-256 still matches the originally verified source. If the
  retry also fails or the source changes, roll back prior replacements and
  preserve any earlier valid completion receipt.
- Never remove or regenerate the source PDF or restart expensive Gemini/TTS
  stages merely because the final candidate promotion failed.

## Regression evidence

- Repeat two case-variant references to one real Windows image;
  verify one canonical manifest entry, without duplicate promotion.
- Inject one transient candidate disappearance; bounded re-stage succeeds.
- Inject persistent disappearance; publication fails and rolls back.
- Mutate the source after staging; publication refuses to promote drift.
- Confirm externally supplied ambiguous figure keys are rejected.
- Cross-platform tests guard distinct filenames colliding by casefold.

The HP pilot's initially failed publication was retried from its **already
generated local scratch outputs**, without any new model calls. The recovered
completion receipt and MP4 hash both verified successfully. That is a
technical recovery, not a replacement for subject-matter approval.

Keep the current Git checkout on local disk and the source/output directories
separate, as described in `LOCAL_CODE_THREE_PC_DEPLOYMENT.md`.
