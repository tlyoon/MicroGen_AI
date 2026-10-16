# Legacy Thomas Calculus Beamer repair — isolated, fail-closed workflow

**Applies to:** MicroGen_AI, not MicroGen_AI_Web.

## Why this exists

The read-only audit of the 63 older ZCA110 Thomas Calculus lecture folders found
60 with incorrect Beamer total-frame counters (`1/1`, `2/1` instead of
`1/N`, `2/N`). The historical `slides.tex` relies on
`\\inserttotalframenumber`; a second `pdflatex` pass corrects the footer
without another Gemini request. Nine of the 60 also have out-of-page content.
These require separate, targeted reflow; a footer fix alone cannot certify them.

The user instructed MicroGen to **assume independent academic approval** of the
material. This does not turn mechanically defective historical PDFs into
technically valid files, nor does it manufacture signed approval receipts.

## Reproduce the offline repair without modifying original lectures

Use the clean, local-disk Git checkout, not the Google Drive-synced old repo.
The `--output` folder must not exist and must be on a local drive:

```powershell
$code = Join-Path $env:LOCALAPPDATA 'MicroGen_AI'
$src = 'G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\1\1.1'
$out = Join-Path $env:LOCALAPPDATA 'MicroGen_RepairCandidates\1.1'
python (Join-Path $code 'microgen_legacy_pdf_repair.py') --source $src --output $out
```

For a page with an independently identified overflow, explicitly opt into a
minimal shrink for **that frame only**, never for the entire textbook:

```powershell
$src = 'G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\1\1.6'
$out = Join-Path $env:LOCALAPPDATA 'MicroGen_RepairCandidates\1.6'
python (Join-Path $code 'microgen_legacy_pdf_repair.py') --source $src --output $out --shrink-frames 12 --shrink-percent 5
```

The command:
- Copies original Beamer inputs and graphics into an **isolated local** directory.
- Runs `pdflatex` twice, checks the new PDF's correct slide counters,
  page content, embedded image streams and geometric dimensions.
- Fails if any *previously visible* original PDF word is missing from the
  candidate. Previously clipped mathematical glyphs may become newly visible;
  these are listed under `additional_visible_words` for a reviewer.
- Refuses the existing target directory, a Drive-backed output directory, or
  a frame with ambiguous existing options; caps shrink at 10%.
- Saves a machine-readable `repair_report.json` for successful PDF candidates.
  Rejected candidates are left in isolated temporary failure directories for
  diagnosis, but never published.
- Does **not** alter `source.pdf`, `slides.tex`, `slides.pdf`,
  `script.txt`, `slide*.wav`, `slides.mp4` or Moodle files in the course tree.

This utility deliberately does **not** create or modify
`.microgen_verified_completion.json`; it is not a publishing tool.

## Verified initial pilots (16 October 2026)

- **1.1**: 17 slides; after two LaTeX passes the footer reads `1/17`
  through `17/17`; body text and embedded images remain identical.
- **1.6**: 16 slides; explicit 5% shrink on slide 12 moves the clipped
  denominator `2` of `π/2` into view. No original visible words disappear.
- **5.6**: 15 slides; explicit 5% shrink on slide 13 makes the previously
  clipped integral-evaluation limit `0` visible. No original visible words
  disappear.
- **6.2 / 6.6**: explicit 5% shrink on slides 8 and 7 respectively also
  passed the isolated technical-PDF candidate gate.
- **3.3, 3.10, 4.2, 4.6, 4.8**: a single 5% shrink did *not* pass the
  fail-closed text-token comparison and remains unapproved; these require a
  manual image/text comparison or a different isolated layout correction.
- **7.2**: footer-only pilot passes technical PDF validation but slide 1
  narration title remains truncated (separate remediation).

## Before any production replacement

**A repaired PDF alone is not a repaired MP4.** The older video may still show
wrong page counters and clipped content. Any accepted correction must be
reflected in the video by re-rendering source-matched slides and preserving the
existing narration voice and timing—or regenerating dependent audio/video
when narration changes. Validate the resulting streams, slide count,
duration, audio consistency and artifact hashes together. Keep a full backup of
the original course folder; publish using the tested single-owner,
candidate-first rollback path and issue a new genuine completion receipt.

For sections **5.6** and **7.2**, the first spoken titles are truncated:
`5.6 Definite Integral Substitutions and the Area` should end
`Between Curves`, and `7.2 Exponential Change and Separable Differential`
should end `Equations`. Do **not** edit only the script JSON and falsely
claim the old WAVs still match. Correct the narration in an isolated candidate,
regenerate the specific TTS WAV with the same provider and voice, then redo
affected audio/video timing and technical QA. Do not substitute another voice
silently.

**Publication status:** no replacement of any of the remaining 63 legacy
lectures was authorized by these technical-PDF pilots. Academic approval is
being assumed per the user's instruction; it is not a substitute for
the technical and provenance checks above.
