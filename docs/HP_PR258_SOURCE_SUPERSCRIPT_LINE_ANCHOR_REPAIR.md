# PR258 — Prevent repeated PDF superscript anchor-reflow failures in source-grounded authoring

## The previously missed failure mode

An original PDF source can encode superscript mathematical notation differently when read by separate PDF extraction modes. The PR247 source discovery uses a bounded PDF text-block extractor, which may join a power such as ten-to-the-ninth into the literal token "109". The existing independent portable contract checks *physical PDF lines* and sees it as separate "10 9" glyph spans. Both representations come from the SAME immutable original PDF, but an otherwise valid original ChatGPT/Gemini lecture fails in the last source/media contract solely because its chosen exact source anchor spans the typographic discrepancy. This happened in the **newly attempted real Serway §1.5**. Repeatedly editing the model draft by hand would violate the owner's efficiency and recurrence-prevention policy.

## Implemented deterministic fallback

New _line_safe_source_anchor and _ensure_source_line_compatible_anchors in microgen_portable_private_authoring_gate.py operate **only after the existing strict source PDF SHA/recreated-packet/section/page/passage/source-copy/numeric checks passed**:

1. Preserve the original source anchor if its normalized form is found directly in the PDF-line text on the same physically cited page.
2. Only if a mismatch remains, strip unstable *trailing words* from the original source anchor to find its **longest unambiguous prefix** still literally present in both the independently cited original source passage and the PDF's line extraction. Require at least 5 original words, 24 original characters, and unique occurrence on the page. Do not substitute synonyms, mutate model-written narration/slide copy, invent mathematical notation, relax source-page or anti-copy requirements, or copy external text.
3. Record private per-slide source passage IDs and SHA hashes of old and adopted anchors, with no original source quotes in the QA receipt.
4. Independently rerun the unchanged portable source/voice/visible media contract to check that the resulting anchor is truly present inside the section bounds. Failure to find a unique safe original prefix remains a hard failure, not an automatic quality waiver.

Legacy source candidate drafts with already compatible anchors preserve them unchanged. No source PDF, figure, voice, model response text or source integrity hash is changed. The original drafted response canonical SHA remains the same, while the compiled manifest records the shortest source-literal repair only if actually needed.

## New real section 1.5 from ChatGPT (original content)

An entirely NEW seven-topic lecture manuscript was authored by **ChatGPT in the active project conversation**, using the private original Serway section 1.5 source packet, not a local language model or paid API. Topics cover estimates instead of false precision, scientific notation/order of magnitude, the square-root-of-ten boundary for magnitude rounding, factor-of-ten reliability, breaths-per-minute lifetime estimates, dimensional time-to-event conversion, and assumptions under revised lifespan. The original source PDF has **2 pages and 15 bounded source passages**, **14 linked** from the seven-topic draft.

Immutable private source:
G:\My Drive\Serway\Serway_1_7\1\1.5\source.pdf
Source original SHA-256:
7f757fee2d28d29d35f395a1400e5f81d9d3bdf4049bf313ba94c8b0dbcc6c62

The first original seven-topic response failed the old downstream literal anchor due exclusively to "109" vs "10 9" in a superscript power. With PR258's new code and the **unmodified original response**, source authoring and slide rendering passed on a fresh private stage with **exactly 1 repaired anchor**. No textbook source PDF was edited, and no academic/copyright permission is implied.
Private original prompt packet:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_SERWAY15_PRIVATE_SOURCE_PACKET.json
Private unmodified original response:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_SERWAY15_NEW_CHATGPT_AUTHORING_RESPONSE_PRIVATE.json
Private automatically repaired source/narration/plan/contract:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_SERWAY15_AUTO_REPAIRED_SOURCE_STAGE
Private seven-slide PDF SHA-256:
a1715b1c838451881380528024930c4e4dcddc5df83f99afb37b2d834a9e28a1
Private slides:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_SERWAY15_AUTO_REPAIRED_SLIDES

A media candidate using existing experimental HP-local Piper voice and Vosk ASR advisory can be produced for internal testing, but this is NOT a locally installed language model, NOT the approved formal production voice, and its output cannot be published. Any video results must be independently rechecked against the source/slide PDF/audio before recorded as passed.

## Regression and safeguards

Synthetic test_microgen_portable_source_anchor_reflow.py covers superscript joined/separated PDF glyphs, exact unchanged anchors, forged source citations, ambiguous repeated text, too-short anchors, and unchanged synthetic source-stage output with zero repairs. New and previous PR247 tests **28 focused passed**. All full HP tests and all four GitHub hosted Windows/Ubuntu Python 3.11/3.12 CI jobs MUST pass on exact head before merge.

Owner policy persists: original MicroGen_AI HP ONLY for code/QA/rendering; ChatGPT/Gemini ONLY for generative content; NO locally installed LLM, unapproved paid APIs, new computer, public textbook/media uploads or automatic publication. Avoid brittle overchecking and do not claim complete semantics or voice authorization. Future steps: extend truthful, source-safe authored subsections and use new anchor gate + existing independent science QA to avoid prior recurrent stalls.

## Actual new seven-slide §1.5 private video and independent media postflight

The 7-topic ChatGPT-original automatically source-anchor-repaired stage was passed through the preexisting experimental/offline Piper WAV, advisory Vosk and FFmpeg H.264/AAC pipeline. This was NOT a local language model and NOT an approved formal production TTS voice. It created a **250.755-second**, seven-slide private candidate MP4 SHA-256 **18d5c4b03af44f12ca57427d7edd86ed5985aafb33098297c3ad8acf56782881**. A separate independent source/media postflight verified 7 WAV file SHA/PCM encodings, decoded seven MP4 midpoint frames and compared pixels against the seven-slide PDF (worst normalized RGB fraction 0.005951), preserved original textbook source PDF SHA 7f757fee2d28d29d35f395a1400e5f81d9d3bdf4049bf313ba94c8b0dbcc6c62, H.264 video/AAC audio, seven narration/slide bindings, 0 targeted pronunciation risk and 0 advisory recognizer term miss. Neither precise phoneme correctness nor academic completeness, figure rights or publication clearance is established.

Private video:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_SERWAY15_FULL_PRIVATE_CANDIDATE_VIDEO\video\lecture_portable_neural_candidate.mp4
Private independent verification:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR258_REAL_SERWAY15_INDEPENDENT_AV_POSTFLIGHT.json
