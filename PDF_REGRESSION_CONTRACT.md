# Shared PDF regression contract

Scope: original MicroGen_AI (not MicroGen_AI_Web). Applies to new PDF handling fixes.

1. Fix causes in shared intake, figure, text, math, and rendering modules. Do not substitute per-section PDF edits for a generalizable correction.
2. Add synthetic regression fixtures for every generalizable defect. Cover both a failing case and unaffected cases.
3. Preserve original source.pdf files byte-for-byte. Keep source content and media private; reports that leave the machine must contain no textbook excerpts, images, or narration.
4. Fail clearly for corrupt, encrypted, inaccessible, or insufficiently searchable inputs. A single failed source must not trigger edits to unrelated PDFs.
5. Reuse SHA/source manifests and existing evidence receipts for unchanged inputs. Recompute only affected validation stages; do not regenerate approved slides, audio, or video just to retest PDF intake.
6. Figure/caption/math ambiguity is reviewed against original source evidence. Avoid false high-confidence claims from lexical or similarity heuristics.
7. Every new shared fix requires focused tests plus the existing root regression suite. Keep CI acceptance and merge policy unchanged.
8. Existing PR262 development changes remain isolated. Never rewrite or reset a dirty checkout when preparing a regression branch.
9. Never install or run local LLMs. Use approved ChatGPT/Gemini paths only when actual authoring is needed; no unapproved paid services or publication.
10. Synthetic tests are pipeline invariants, not proof that academic content, figure rights, or complete finished lectures have been accepted.

Acceptance: previously repaired input categories remain covered by tests; an unseen PDF is handled without source-specific code changes, or is explicitly classified as an unsupported/new defect.
