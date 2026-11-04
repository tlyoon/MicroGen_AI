# First-class autonomous scientific-content gate

This implementation is for the **original API-based MicroGen_AI**, not the
Selenium/Web project. It follows
`docs/AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md`: no mandatory human
sign-off, no fictitious certification and no loops fixing one particular PDF.

## Where it runs

The resumable `microgen_batch.py` stage order is now:

```text
figure_extraction → figure_mapping → figure_merge → slides
→ narration → science_qa → tts → slide_slicing → video → published
```

A normal new lecture cannot synthesize paid audio before passing the independent
`science_qa` stage. `--stop-after narration` still stops before the additional
API call, and `--stop-after science_qa` permits a bounded private evaluation
without TTS or video publication.

The new stage uses an independent **Gemini request** with the *actual* source
PDF page text, *actual* rendered slide PDF text, original narration and exact
speech-facing sidecar, then evaluates each slide for source-contradicting
scientific statements, units, numeric claims and figure descriptions. This is
an independent invocation of a language model, **not guaranteed independent
scientific knowledge**. It never reads a previously self-graded authoring
summary instead of the real outputs.

The structured model response must cover every slide in order. Invalid,
missing or contradictory responses fail; silent progress is not permitted.
The public status says only `SOURCE_GROUNDED_MODEL_SCREEN_PASSED`, never
`scientific_content_perfectly_verified` or `human_approved`.

## Bounded correction policy

**PR #272 extension:** Exactly source-quoted changes may be made to one
unambiguous, literal slide *text* passage as well as up to three total
narration/slide corrections per bounded assessment. Narration changes must
agree across `script.txt`, `narration` and `tts_text`.

For a slide change the engine requires a unique literal in its original
`slides.tex` and rendered PDF text; the old and new text must contain no
unsafe TeX control characters, math delimiters or macros. It compiles a new
candidate deck with `pdflatex -no-shell-escape` in isolated local scratch,
checks unchanged page count, unrelated slide text and embedded original figure
bytes, and passes the candidate *rendered* slides to a second source-grounded
Gemini review. Only then are the candidate PDF/TeX and any revised narration
committed together, with rollback on failure. If WAVs/MP4 already exist, no
source text correction is permitted without separately regenerating downstream
media. Original `source.pdf` and protected media remain unchanged.

TeX equation rewrites, visual figure-semantic errors and nonverbatim scientific
claims are **not** silently fixed; they remain explicit blockers with immutable
private diagnostics. The small bound prevents repeated PDF-specific fixing
loops. This contract does not equate model agreement with guaranteed scientific
correctness.

Passing receipts now also bind the science QA and slide-repair implementation
hashes. The batch can recover an exact previously completed QA receipt after a
checkpoint crash, avoiding duplicate model costs, and updates upstream stage
fingerprints after an accepted correction to prevent needless regeneration.

A successful machine audit creates
`.microgen_autonomous_science_qa.json` tied by SHA-256 to the exact
`source.pdf`, `slides.pdf`, `slides.tex`, `script.txt`, and
`script_tts.json`. The resumable batch verifies this marker and includes the
QA implementation in its dependency fingerprint. Any later content change
invalidates it. A single failed stage cannot be marked complete.

## Scope and limitations

This resolves the **missing normal production integration** of model-based
source consistency screening and source-verbatim narration correction. It does
not claim that all physics is correct: additional deterministic mathematics,
equation/figure, conceptual coverage, and independent acoustic checks remain
part of further development. Nor does a successful source screen imply that
word-level equation highlighting is independently verified.

The separate release audit still requires SHA-bound independent acoustic
evidence and every final video **strictly below 600 seconds**. For example,
the existing private Chapter 2.1 MP4 is approximately 627.66 seconds, so it
still requires automatic compliant segmentation. This milestone does not
pretend that adding a new QA stage has repaired that older video.

Production TTS remains Gemini Flash-Lite/Kore by default. Google Cloud TTS
remains explicitly opt-in, and no local language model is required. QA and
textbook outputs remain private. Software/technical QA is separate from
external publication permission for copyrighted material.
