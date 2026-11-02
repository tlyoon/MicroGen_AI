# PR247 — private source-grounded lecture authoring handoff and validation gate

## Why

PR244 discovers source-bounded PDF passages; PR245 checks original figure pixels and caption proximity; PR246 verifies a narrow typed mathematical claim. The remaining barrier to a general one-call lecture generator is **original pedagogically accurate authored content** (topic selections, slide wording, narration). Earlier 16-slide Serway §1.2 production relied on a manually authored content manifest. This PR creates the reusable source-to-authoring handoff and reject-or-package workflow, without pretending a locally unavailable authoring model can write trustworthy new content.

The new `microgen_portable_private_authoring_gate.py` supports two explicit actions:

1. From an original private section PDF, a chapter start marker, and a next-section marker (or declared end-of-PDF), generate a **private-only source evidence packet**. It contains SHA-bound source paragraph IDs, source page, PDF block bbox, literal passage text, figure-number mentions, and a structured request for an authorized independent lesson writer. **No external provider is invoked by this module.**
2. Given an independently authored JSON draft matching the exact packet hash, automatically validate and produce the standard, fresh, transactional source-bound `source.pdf`, `narration.json`, `plan.json`, `contract.json` plus private QA report. All output follows existing `audit_portable_contract` checks, and can be rendered with `microgen_portable_slide_render.py` or the private offline candidate-video pipeline.

Sample private command:

```text
python microgen_portable_private_authoring_gate.py --source <existing-private-pdf> --start-marker "<section-title>" --next-marker "<next-title>" --section-id "1.2" --new-private-packet <fresh-private-packet>.json
python microgen_portable_private_authoring_gate.py --source <same-private-pdf> --start-marker "<section-title>" --next-marker "<next-title>" --section-id "1.2" --draft-response <authorized-original-writer-response>.json --new-private-stage <fresh-private-directory>
```

## Acceptance checks

- Require exact original PDF SHA and canonical packet hash; protected input source remains unchanged. Source passage IDs and source page are checked for each slide; source anchors must be literal passages inside the chosen section. Required technical terms must appear in the cited source, original narration, and visible title/bullets.
- Each of 2–60 topics has a distinct slug, at least 60 and at most 250 words of original English narration, and printable bullets/title within renderer limits. Topic order must follow source-page order.
- Reject any **12-token contiguous quotation** from the bounded original source, repeated 10-word narration sequences beyond the safe ratio, or numeric tokens absent from the specifically cited source passage. These conservative checks are *indicators* of source copying or unsupported statements, **not proof of independent semantic correctness or copyright compliance**.
- When legitimate numbers occur in the source figure/equation rather than the extracted prose passage, a topic may provide an optional bounded `source_numeric_evidence` containing the original source page, PDF crop rectangle, original raster SHA and exact numeric tokens. Each is validated against the original PDF itself, below the actual section heading and before the following-section marker. This lets original textbook §1.2's `25.0`, `50.0`, and `23.3` be cited without allowing fabricated measurement values.
- Fresh output only, never overwrite or write into protected Google Drive. The authoring service does not choose a model, upload user textbook material, invoke a provider, authorize narrator rights, or publish media. Failure is explicit and leaves no partial stage.

## Actual real textbook validation on authorized HP

Real original source: five-page Serway §1.2 `Modeling and Alternative Representations`, immutable SHA-256 `814ce3e174b730271b04bbec4284bb4a15930d5026a2fcbb5148e0cf5ec018cb`.

**The previous 16 original teaching scripts were re-ingested**, rather than falsely claimed as newly machine-authored. The input package used the independently discovered 34 original source passages, 19 linked passage IDs and 2 original-PDF raster numerical evidence regions, generating fresh standard source/narration/plan/contract and a 16-page private candidate PDF. There are 15 other source passages without literal topic association, an advisory inventory, **not** 15 omitted concepts.

Real private packet `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR247_REAL_SERWAY12_PRIVATE_PACKET.json`. Private authoring result `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR247_REAL_SERWAY12_REINGESTED_PRIVATE_STAGE`, rendered PDF SHA `1f35c87102d5a0218c46d205389847d6cbb04735e9e443f8b5ca12897b84bc38`. Source unchanged. No copyrighted source, examples, narration, or media included in repository.

Tests in `tests/test_microgen_portable_private_authoring_gate.py` are wholly synthetic: successful end-to-end candidate-stage-to-slide PDF, forged packet hashes, stale source, copied phrases, fabricated numbers, wrong source references, missing terms, excessive narration copying, invalid type/length/approval, output collision, original source exact figure/equation number evidence and boundary-borrowing.

## Explicit limitation and next task

**This PR fixes the authoring interchange and source/copyright-quality gate, not the fully automatic original-content generator.** No offline language model service or browser-based generative model was available on the authorized HP checkpoint during this task. Production-level scientifically reliable narration requires a separate approved model authoring backend and/or independently verifiable original-content synthesis, with semantic QA (beyond exact term/string checks). Only plug in an authorized backend without unapproved paid cloud calls or movement of private textbook material.

Neither this gate nor previous mathematical/figure QA certifies academic completeness, all physical assumptions, textbook figure rights, production narration voice, or publication. All publication/voice flags remain false.

## Independent packet re-verification

The draft and packet hashes are not simply trusted together: the authoring gate **independently rediscovers the bounded original PDF passages** and compares its canonical packet SHA with the supplied packet before accepting any authored response. A forged packet plus correspondingly forged draft hash is rejected. This source-rebuild check is covered by a separate synthetic test.
