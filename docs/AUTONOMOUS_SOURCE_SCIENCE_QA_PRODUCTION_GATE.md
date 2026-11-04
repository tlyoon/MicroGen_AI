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

Only exact **narration** substrings may be repaired, and only when the proposed
replacement is an actual source-PDF passage. Each change must be:

1. A clear source-contradicting error reported by the separate reviewer.
2. A unique literal occurrence in `script.txt`, `narration` and `tts_text`.
3. Replaced by a source-quoted literal phrase, not an unsupported model rewrite.
4. Accepted in a second, bounded, complete source-slide-narration review.

At most three such substitutions are allowed. Both text files update together
with rollback on failure. No WAV/MP4 or original PDF is touched by this QA
stage. Unresolved scientific slide/equation errors, forged source citations
and provider failures *block that stage*; they do not trigger unbounded PDF
regeneration. Later autonomous improvement may add separately verified,
source-preserving **slide** repair in a new change request.

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
