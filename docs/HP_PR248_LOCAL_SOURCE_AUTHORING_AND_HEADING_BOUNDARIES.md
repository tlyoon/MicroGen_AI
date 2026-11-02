# PR248 — HP-local optional original lecture authoring and real-new-section demonstration

## Background and correction

PR247 introduced a rigorous private authoring interchange but had no callable content-generation backend. This PR adds `microgen_private_local_authoring.py`, an opt-in **HP-loopback Ollama chat** connector. It constructs a PR247 PDF source-evidence packet, requests an original structured teaching draft from an explicitly named on-device model, validates the untrusted JSON against actual source text and geometry, and transactionally produces the existing source-bound narration/slide/contract stage. Accepted content stays *candidate*, not academic-certified or publishable.

**No paid calls or external uploads**: the tool accepts only `http://127.0.0.1:<port>/api/chat`, disables proxies and HTTP redirect following, requires an explicit local model name, limits input/response sizes and numeric retry/timeout, and never silently falls back to a hosted provider. This backend does NOT install or assert the presence of Ollama, its model weights, or any formal voice. An absent local service fails clearly without creating a stage.

## Example use after an explicitly authorized local model is actually installed

```text
python microgen_private_local_authoring.py --source <private-source-pdf> --start-marker "Dimensional Analysis" --next-marker "Conversion of Units" --section-id 1.3 --model <local-ollama-model-tag> --attempts 2 --timeout 90 --new-private-stage <fresh-private-output-directory>
```

The writer is given the complete locally protected source packet and explicit constraints (2–60 distinct ordered topics, 60–250 spoken words, short original bullets, passage and page IDs, clear source anchors and required terms). Only model drafts failing the authoring acceptance gate receive a bounded retry with a brief diagnostic; missing local services, malformed model envelopes, invalid endpoint, bad credentials or network failures stop. The gate cannot prove semantic truth or copyright clearance, and its 12-word continuous copy and numeric checks remain conservative indicators.

## Fixed a cross-layer first-page heading boundary defect

The old source discovery (PR244) chose the **last PDF text block containing the section title**. A section that repeats its title in its narrative, such as real Serway §1.3 Dimensional Analysis, had most of its first-page conceptual material incorrectly excluded. The original section contract (PR239) similarly used `rsplit(start_marker,1)` on full first-page text, losing prior genuine paragraphs when the section title was discussed later.

The corrected `microgen_source_passage_discovery.py` identifies actual numbered heading lines by their prefix and suffix, can disambiguate running headers, recognizes legacy PDFs containing literal escaped-newline markers, and rejects body-text mentions. The `microgen_portable_section_contract.py` now performs physical page/line-bounded source-anchor checks using **the same geometric heading identification**, excluding the previous section and following section without using last text mention. A PDF text block containing a heading and paragraphs no longer causes whole paragraphs to be discarded. Adversarial synthetic tests cover source body mentions, numbered-heading vs narrative, other-section content and older legacy combined blocks.

## New real section: Serway §1.3 — Dimensional Analysis

Source: `G:\My Drive\Serway\Serway_1_7\1\1.3\source.pdf`, private original three-page PDF SHA-256 `181f0f361809d90daf72fce1bf50bcf2b88fbf37fc59ed181411266b53cb5ae8`, unchanged. It contains §1.3 on first two pages, and a later next-section heading §1.4 on the final page. **After the heading fix**, PR244 discovers **24 actual bounded source passages**, compared with only 16 passages under the defect.

A new **seven-topic original teaching draft** was written in the current ChatGPT development session, in fresh educational wording, not reused from prior §1.2 and not produced by a running on-HP Ollama service. The independent PR247 gate validated it: **7 topics**, 15/24 source passages explicitly linked, nine passages without declared anchors as advisory triage, 7-slide PDF generated with SHA-256 `6c35fb6ea8f48d5286cf9e5ffc60e079e54420d34cf4e9411369d6b096eadfe2`. The seven topics include dimensions versus units, dimensional consistency, position and acceleration, proportionality scaling, speed, circular acceleration and limitations of dimensional checking. This is a source-bound *pilot*, not proven comprehensive or textbook-equation complete.

Original PDF and all textbook passages and newly generated original lecture text remain exclusively on HP. No source PDF, textbook figures, narrated WAVs, private packets or private video are included in GitHub.

Private HP files:
- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_SERWAY13_CORRECTED_SOURCE_PACKET_PRIVATE.json`
- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_SERWAY13_NEW_ORIGINAL_DRAFT_V3_PRIVATE.json`
- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_SERWAY13_FRESH_SEVEN_TOPIC_PRIVATE_STAGE`
- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_SERWAY13_FRESH_SEVEN_TOPIC_PRIVATE_SLIDES`

## Verification and limitations

- Synthetic: `tests/test_microgen_private_local_authoring.py` covers valid local-model response, bounded retry with original packet, failure containment, off-host/cross-scheme URL refusal, malformed response, missing local model, preexisting output, and retry-budget validation, with no network or paid calls.
- Existing source-discovery and portable-section regression expanded. Source heading can reappear in body text without false section trimming.
- Actual HP-local Ollama service was **not found** at this checkpoint; the backend was verified using simulated local-model responses and the new **in-chat-authored** real subsection. Do not describe actual model inference on HP as having occurred.
- Existing offline Piper voice is still a nonformal candidate. Academic semantic completeness, rights, and production-quality narrator remain not certified; all `publication_allowed=false`.

Next priorities: confirm/connect an approved actual local model and produce a never-before-authored subsection autonomously; then independently check scientific entailment and formula dimensions across original diagram/equation/slides; preserve strict source rights, no academic manual approval gate, and retain only bounded nonbrittle audio QA.

## Independently verified complete offline private pilot video

The fresh Serway §1.3 candidate passed source->seven-slide PDF->offline Piper WAV->Vosk advisory->FFmpeg H.264/AAC video. The new MP4 is **311.407 seconds**, **4,539,201 bytes**, and SHA-256 `8f50a8ba00cd6e99fd99d49c558dd2bf0b4d1a9975d84a45c2ead6361eefa16a`, preserved privately at `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_SERWAY13_FRESH_SEVEN_TOPIC_FULL_OFFLINE_VIDEO\video\lecture_portable_neural_candidate.mp4`. The separate independent HP postflight in `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR248_REAL_SERWAY13_INDEPENDENT_POSTFLIGHT.json` rechecks all seven WAVs and the source/media SHAs, confirms video H.264 and audio AAC, decodes all seven slide-midpoint MP4 frames and compares to independently rendered slide PDF images (maximum normalized average RGB difference **0.005911**). The recognition advisory reported **zero targeted pronunciation risks and zero term misses**, which does not prove full phoneme-level correctness. The candidate was generated from newly GPT-authored seven-topic copy in this chat, **not from locally active Ollama**. This is not a complete, rights-cleared, formally narrated or publicly released lecture.
