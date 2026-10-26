# HP-only MicroGen_AI completion-first — two genuinely fresh Section 2.5 technical video candidates

**26 October 2026. Original `tlyoon/MicroGen_AI`, NOT MicroGen_AI_Web.**

## Owner contract and changes

**HP only** for original-package local work. Dell-115 is reserved for MicroGen_AI_Web. GitHub-hosted Actions CI is separate and allowed. No Yoga6/Zenbook, protected G: dirty working trees, historical course WAV/PDF/MP4 edits, Whisper, or video publication. The **My Drive root copy of the generated 23-page slides** was specifically authorized. Do not mistake private My Drive file review for approval/publication of new lecture videos.

The owner committed us to three milestones: **(1) complete one accepted HP textbook→video lecture, (2) prove generality on 2–3 different subchapters, (3) integrate tested PR stack into stable version and release**. Do not substitute PR counts or hypothetical QA checks.

The fresh original textbook-to-figure-map-to-23-Beamer-slides-to-narration-to-23-Chirp3-TTS pipeline has now succeeded on HP using explicit authorized existing providers. The full original spoken TTS audio is **910.54267 s**, so it cannot be a single sub-600-second lecture. Existing generic multipart code required a reviewer-approved concept/scene manifest and older `gen_video_v22.py` produces unhighlighted still-slide clips; falsely marking semantic review passed to release two videos was not acceptable. This increment proves two *nonpublishing technical previews* with source-bound **offline Vosk word-position candidates** and true encoded video checks, then independently checks sample highlights and controls from **actual encoded MP4 frames**.

## Reusable implementation

- `microgen_fresh_split_highlight.py`: checks all 23 WAVs are true 24-kHz mono PCM16, binds source PDF/slides PDF and individual WAV SHA-256, calculates optimal complete-slide partitions under a **570-second** safety margin without dropping or duplicating slides. Uses existing local Vosk model on **current** slide WAVs and conservative unique-token matches to actual Beamer PDF text boxes. No offline ASR guess or mere overlap becomes mathematical or figure semantic approval; ambiguous/repeated/equation symbols are excluded. Re-renders original PDF-derived frame RGB data at 960×540, 8 fps, highlights only timed candidate literal word rectangles, and muxes source-concatenated lossless ALAC audio. Independently decodes every final MP4's PCM and requires **bit-identical** SHA against the original concatenated WAV audio. Outputs SHA-pinned receipt with **publication_allowed=false**. Does not call any API, upload, replace original media, or overwrite earlier outputs.
- `microgen_fresh_split_pixel_qa.py`: independently seeks frames from the actual MP4, compares decoded pixels against the original source PDF and independently computed expected highlight regions, and checks **negative no-highlight controls** on each slide. The report remains unapproved even when positive and negative pixel samples pass.
- `tests/test_microgen_fresh_split_highlight.py`: dynamic split, source-binding/rejected wave formats, wrong slide count, token ambiguity, 10-minute bounds and visual difference controls. No fake source/cue academic acceptance.

## New REAL HP §2.5 pilot

- Original source: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY\2.5`; original textbook `source.pdf` SHA `dbc34b5de194c3eedcfc686dfabacc903cc45d858b7a5240912a358d2f2f384b`, fresh slides `slides.pdf` SHA `4f13819a17c100fd85b13348ec53d39b4012828c1aecc18d66885ba7a390b231`. 23 newly generated 24kHz WAVs share one Google Cloud Chirp3 voice `en-US-Chirp-HD-F`, TTS provenance receipt SHA `2bf7ae11811c74f604e8fba10bf312039c3fa5ff99f72b1d461d46168f0db968`.
- Isolated **unpublished technical candidate directory**, existing on HP only: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SPLIT_HIGHLIGHT_PREVIEW_V1`.
- **Part 1** `Thomas_2_5_part01_UNAPPROVED.mp4`: slides 1–13, **464.67 s = 7:44.67**, SHA `7ebad89afaa88e6368064e3501927d174b129b5350fedb30f197e40a450276bd`.
- **Part 2** `Thomas_2_5_part02_UNAPPROVED.mp4`: slides 14–23, **445.88 s = 7:25.88**, SHA `74f1874ec505de710732d35d03ed6aa9bfa4dd782ad64592b46672d6425f6779`.
- All 23 original slide soundtracks concatenate exactly without insertions: **each MP4's decoded audio PCM is bit-identical** to its part's concatenated WAVs. The encoder verified both complete MP4 durations and all slide groups preserve order.
- From fresh actual WAV offline ASR, **168 plausible PDF word highlight rectangles**, 896 frames with at least one candidate cue, 7285 rendered frames across both previews. This is partial literal word visual highlighting, **NOT complete element-level narration/figure synchronization**. The source cue report SHA is `da3542058b5ed29d8ea7a19fc276680c572eae61097809336d3869b2823ae730`.
- **Independent actual video pixel inspection:** **23/23 candidate highlight positive samples** and **23/23 no-highlight controls** passed on MP4 decoded frames, one each per slide. QA evidence `independent_actual_video_pixel_qa.json` SHA `318c610620e014e110681eb9eea69df604bfa89a50544e6a4656e647376c0336`. Full split-video receipt `split_preview_receipt.json` SHA `c792580e6ed9ff9d216a2f5e26a04d5c0cd48a709f3b3de4f0bf460c8fbb945a`.
- User's new slide PDF was **copied as an additional file** to `G:\My Drive\MicroGen_Thomas_Calculus_Section_2.5_Slides_2026-10-26.pdf`; HP copy SHA matched `slides.pdf`. **Authenticated Google Drive metadata separately confirmed** root folder ID `0AAK3dd2e0P7wUk9PVA` = My Drive, uploaded file ID `1FFcJYh3MHqPalhWucn-6e81Gd32Unqr5`, PDF MIME and 505069-byte size. User link: `https://drive.google.com/file/d/1FFcJYh3MHqPalhWucn-6e81Gd32Unqr5/view?usp=drivesdk`.

## Nonnegotiable remaining release blockers

**None of these technical preview checks certify academic mathematics or figure quality, pronunciation, voice identity by listening or complete figure/spoken-element alignment.** Existing TTS risk inventory flagged 69 potential pronunciation problems across 16 slides; these are *candidates* not diagnosed errors. Figure 2.38 was manually recovered as an exact source-page crop but this self-healing method must be integrated into normal generation before M2. Likewise the original 20 figure crops narrowed to 14 Gemini-labeled figures + the recovered one; 6 unmapped crops and source figure coverage/semantics require source-backed review. The two videos must **not** be posted to YouTube/Moodle or marked publishable. Need a concept/scene review at slide-13 boundary, independent true spoken-math/figure sync verification and approved phonetics. Remaining regression tests and hosted CI are separate from domain signoff.

## Final independently run HP regressions

- Focused new source-bound split/visual QA tests: **15 passed** (before independent complete tests), including actual 23-slide pilot partition test and mathematical-symbol ambiguity guard.
- Full original MicroGen_AI HP `python -m pytest tests -q`: **919 passed, 4 skipped, 1 benign warning, 101 subtests; exit 0**. Previous #194 baseline: 904 passed, 4 skipped.
- HP `python -m unittest discover -s tests -q`: **593 tests passed, 3 skipped; exit 0**. All actions HP only; no billable provider invocation in split/pixel code.
- This PR must not be merged until the owner has accepted the remaining math/figure/phonetic/voice issues or approved release conditions; outputs remain isolated as `*_UNAPPROVED.mp4`.
