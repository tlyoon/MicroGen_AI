# PR260 — Interior source-heading boundaries and new Serway 1.6

## Root failure fixed

The prior source passage discovery, PR247 original-content authoring gate and independent portable lecture contract all incorrectly assumed that the NEXT textbook heading was on the final PHYSICAL PDF page. But real section 1.6 Significant Figures source.pdf has 4 pages, the real NEXT heading Summary is at the bottom of page 3, and a whole extra page of next-section material follows it. Prior authoring packet generation failed despite an unambiguous next-section boundary.

The common _find_section_end_page now searches genuine physical text-heading lines across ALL source pages, favoring true page body headings over repeating running headers and selecting the earliest real next heading AFTER the first original start heading. Its exact original page index/bbox is used by:
- Source passage discovery, excluding the rest of the end-heading page and ALL following pages.
- Independent PR247 source-to-narration/visual academic contract, clipping source page lines and blanking content of any subsequent pages.
- PR247 optional source numeric crop sidecar, denying any numeric support from the next section or appended pages.
- New source metadata reports original next-heading page and number of trailing PDF pages excluded.

No original copyrighted PDF is modified, no boundary or source SHA rule relaxed, and no heading is invented. Missing or reversed headings remain rejected. Prior source-formatting and source-figure provenance fixes are preserved.

## NEW genuine Serway 1.6 candidate

Original private PDF G:\My Drive\Serway\Serway_1_7\1\1.6\source.pdf SHA-256 4045e791d20868b1e492670efa2aeb39455719ffca68c86f27364b122882db40. Four physical pages, true target ends at Summary on original page 3. Newly independently bounded source packet: 21 passages, none from page 4. ChatGPT in THIS conversation authored 10 new teaching topics, citing all 21 passages, for measurement uncertainty, significant digits and zero ambiguity, multiplication/division rules, disc-area precision, addition/subtraction decimal places, rounding and tie-to-even, delaying rounding, and a room-carpet area application.

The existing private SHA/citation/anti-copy/numeric source gate and full slide renderer accepted the original final V4 draft and produced TEN source-bound teaching slides, SHA-256 8824a093842eba8ad57b25eea42d0c4516a2a8bea977912b641bec2fec4d6482.
Private original packet: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_SERWAY16_PRIVATE_SOURCE_PACKET.json
Private ChatGPT source response: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_SERWAY16_CHATGPT_ORIGINAL_V4_RESPONSE_PRIVATE.json
Private stage: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_SERWAY16_CHATGPT_SOURCE_STAGE_V4
Private ten-slide PDF: %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_SERWAY16_CHATGPT_SLIDES_V4\slides_teaching_candidate.pdf

Any experimental Piper/Vosk/FFmpeg media is a private offline QA candidate. Piper is a TTS system, NOT a local language model, and is NOT an approved formal narrator; copyright, academic completeness, phoneme correctness and publication rights remain unproven.

## Synthetic regression and next work

New tests/test_microgen_interior_section_boundary.py uses a synthetic 4-page PDF where genuine next heading is on page2, later pages have extra next-section text and a misleading running header, verifies source discovery and authoring/media gate both exclude unrelated pages, and missing heading still rejects. All 32 new+existing targeted source/authoring tests pass. Full HP root pytest plus hosted GitHub 4/4 Windows/Ubuntu Python3.11/3.12 CI pass on EXACT branch head required before merge.

Authorized machine: HP desktop only for original MicroGen_AI. NEVER install/run local LLM or use unapproved paid cloud APIs, other machines, or public protected textbook uploads. Only ChatGPT/Gemini used for ORIGINAL science content authoring.


## Full new Serway 1.6 private media candidate independently postflight verified

The NEW ten original ChatGPT-authored lecture slides were converted using the preexisting experimental HP-only Piper synthesis, Vosk ASR advisory, and FFmpeg video pipeline. This is NOT a locally installed language model and is NOT the formal production voice. Private ten-slide MP4 duration is 375.814 seconds; H.264/AAC and SHA-256 d2ba3e0f2c70d9305bb44e196d97a0004e6abe33d6b5ab4b14d50307673a8ebf.

An INDEPENDENT second postflight verified the immutable original 4-page source PDF SHA 4045e791d20868b1e492670efa2aeb39455719ffca68c86f27364b122882db40; all ten original PCM WAVs against independent audio SHA receipts; all ten decoded H.264 midpoint video frames against the ten pages of the newly rendered source-bound slide PDF, with worst normalized average RGB fraction 0.00591. No severe targeted ASR pronunciation hazards; ONE advisory recognizer term miss, which is NOT a pronunciation certainty or brittle development blocker.

Private video:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_SERWAY16_FULL_PRIVATE_CANDIDATE_VIDEO\video\lecture_portable_neural_candidate.mp4
Private independent postflight:
%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261103_HP_PR260_REAL_SERWAY16_INDEPENDENT_AV_POSTFLIGHT.json

This candidate is NOT authorized for publication: complete scientific academic coverage, full phonetic correctness, formal voice approval and copyrighted textbook rights have NOT been certified.
