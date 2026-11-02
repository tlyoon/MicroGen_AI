# PR257 — Reuse existing original figure, vector-equation and typed-math QA in multi-section audits

## Rationale

PR256 independently rechecked source-bound dimensions, SI unit ratios and narrowly defined spoken scientific conclusions across multiple earlier lecture stages without rebuilding any media. It intentionally excluded PR246's original-figure and source-typed mathematical proof, leaving §1.2 as "zero of these checks" despite already having a strong source-verified right-triangle calculation and several source-verified figure crops. The omission was a false impression of absent mathematical QA rather than an actual absent capability. This PR closes it **by reusing the prior proven verifiers**, not inventing a parallel heuristic or making the little HP computer install a language model.

## Integration with prior exact provenance gates

New microgen_private_original_figure_math_reaudit.py calls the EXISTING source renderer's checked_figures and the preexisting original-PDF safe verifiers:

1. checked_figures verifies each stage figure filename and complete SHA, actual image, no symlinks.
2. checked_equations verifies source vector equation geometry, source section boundaries and the SHA of the original PDF raster at the exact equation clip.
3. checked_source_figure_regions independently rerenders the source PDF at the original figure PNG pixel scale, checks byte-identical RGB pixels, exact figure label and nearby source caption position.
4. verified_source_math_claims recomputes only the PREEXISTING narrow formula "right_triangle_tangent_height", with source literal distance/angle, independently verified source equation answer, and correct rounding at source-stated precision.

The PR256 multi-section scientific audit now invokes this reusable helper for every private stage in addition to the previous PR249/251/252/255 checks. It freezes source figure files alongside original PDFs/contracts/narration/visual plans and rejects the full batch if a source figure or input changes during validation, or any typed figure/equation/math claim fails. All proofs remain scoped, with no assertion of general science semantics, source figure caption meaning, copyright permissions, or formal voice quality. It does not render slides, audio or videos.

## Real source validation on authorized HP

Rechecked exactly the previously private original Serway §1.2, §1.3 and §1.4 source PDF and stage bundles. All original source SHA values are unchanged and remain in private G:\My Drive\Serway\Serway_1_7\1.

New private report:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR257_THREE_SECTIONS_FULL_SCIENCE_PRIVATE_REPORT\multisection_private_science_receipt.json

The report contains **only** section names, hashes, counts and explicit unverified flags, never textbook wording, original figures, scripts, or WAV/video. Verified counts for three sections/29 previously authored topics:
- Four source-identical original PNG figure raster areas with original nearby figure-label evidence (all §1.2).
- One exact original PDF vector-equation source crop (§1.2).
- One independently calculated right-triangle tangent height of 23.3 metres from 50.0 metres and 25.0 degrees at the printed precision (§1.2), with existing original figure and source equation evidence.
- Three L/M/T typed dimensional equalities (§1.3).
- Three source-linked typed SI conversion/strict speed-limit claims (§1.4).
- One automatically scanned narrated unit equivalence (§1.4).
- One independently source- and SI-consistent spoken speed-limit conclusion (§1.4).

These are distinct narrow checks; counts are NOT comprehensive learning-outcome or semantic-coverage scores. All publication_allowed=false.

## Tests and policy

New synthetic tests test_microgen_private_original_figure_math_reaudit.py check correct handling of empty optional figure/equation/typed-math inventory, forged/missing original figure path, unproven source equation crop, and invented typed right-triangle claim. Existing PR256 multi-section provenance regressions remain active. 19 new+related focused tests passed.

Permanent owner restriction: original MicroGen_AI HP desktop only; only ChatGPT/Gemini for *authoring*, no local language models (Ollama/Llama/Qwen), unapproved paid APIs, or private source uploads. Existing offline candidate Piper TTS is NOT a locally installed language model and remains nonformal; nothing is published. Full HP root pytest and four GitHub hosted Windows/Ubuntu Python 3.11/3.12 jobs must pass on exact commit before merge, then clean sync to origin/main.

Next priorities: use the richer private science audit to guide more REAL newly authored sections with ChatGPT/Gemini; prioritize outstanding clear source/figure issues, regress old fixes, avoid repeated work or invented scientific certification.
