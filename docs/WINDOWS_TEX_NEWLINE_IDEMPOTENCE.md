# General Windows Beamer newline regression, PR #277

On 4 November 2026, the first genuinely new source-to-acceptance
Version 1.0 pilot (Serway Section 2.2) **failed at slide compilation**,
after extraction, figure mapping and merging passed. The generator
reported `Missing $ inserted` after its four bounded repair attempts.

This was not resolved by repeatedly changing that PDF. An isolated,
source-independent reproduction uncovered a cross-platform bug in
`gen_slides_v20.py:clean_pause_in_place`:

- The function detected CRLF input and explicitly converted its normalized
  LF text back to CRLF before saving.
- `Path.write_text` opened the file in text mode and performed **another**
  newline conversion on Windows: `\r\n` became `\r\r\n`.
- Later calls normalized those corrupt endings into extra blank paragraphs.
  These can appear **inside Beamer display-math blocks** (e.g. `\[ ... \]`)
  and trigger a late `Missing $ inserted` at `\end{frame}`.
- An exact extraction of the original production function proved the
  exponential corruption: **6**, then **12**, then **24** CRCRLF byte triples
  on three consecutive calls to the same synthetic TeX file.

**General fix:** Write the already-normalized UTF-8 bytes exactly using
`Path.write_bytes`. Do not double-transform the line endings on Windows.
The function remains responsible only for removing `\pause` commands,
not for rewriting source equations, figures or academic content.

**Proof:** The four portable tests in
`tests/test_microgen_slides_crlf_pause_idempotence.py` exercise the actual
production function (without importing the top-level Gemini client):
- Repeating the cleanup four times preserves exact CRLF bytes and display
  math without introducing blank lines.
- Both inline and standalone `\pause` commands are removed exactly once.
- LF inputs remain byte-identical.
- Legacy CR-only inputs remain byte-identical.

An HP MiKTeX acceptance fixture further applied four cleanup passes to a
CRLF Beamer deck with display fractions, then compiled it twice using
`pdflatex -no-shell-escape -halt-on-error` and verified the resulting PDF.
No Gemini requests were made for this proof.

This general regression is necessary for Windows and is not an approval
to replay and overfit the failed Section 2.2 output. After full offline
regressions and GitHub Windows/Linux CI, Version 1.0 needs a **second
completely fresh source** to achieve the independently established
end-to-end acceptance condition. No v1.0 tag or media publication is
authorized merely by fixing this error.
