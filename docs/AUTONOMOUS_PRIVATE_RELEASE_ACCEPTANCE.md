# Private unified autonomous technical acceptance — PR #276

**Original API-based MicroGen_AI**, HP-only development/test. Follow the
authoritative `AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md`.

## Integration and scope

```text
source → figures → slides → narration → science_qa
→ Gemini Flash-Lite/Kore TTS → acoustic_qa
→ slide_slicing → video (auto-parts if long) → acceptance
→ [separately controlled external publication, not authorized here]
```

`--stop-after acceptance` gives a **bounded private full technical
acceptance campaign**. It makes no external publication attempt. The normal
batch never classifies a generated MP4 as accepted merely for being nonempty.

The new `microgen_autonomous_acceptance.py` gate requires ALL of:

1. Exact, implementation-bound source-to-slide scientific model-screen
   acceptance (PR #271/#272), rendered slides, checked narration, and
   no unresolved recorded source contradictions.
2. Actual source/WAV/voice SHA provenance, PCM checks and separate
   `gemini-3.5-flash` and `gemini-3.8-flash` recognizer evidence for
   **every** slide (PR acoustic QA). Unknown or mismatched audio blocks.
3. Original source crop/figure composition receipts and all currently
   referenced figure files. Unmapped source crops appear as explicit
   advisories and are never silently asserted to be scientifically irrelevant.
4. All required slide PDF/WAV pairs and actual FFmpeg A/V stream/duration
   verification. If `slides.mp4` is >=600 seconds, the verified deliverables
   must be a complete SHA-bound, correctly ordered set of automatic whole-slide
   parts, each **strictly <600 seconds**, with no missing/duplicated slides
   (PR #273).
5. The pre-existing strict release policy evaluated under its default
   `autonomous` mode, including normalised pronunciation preflight,
   lexicon, voice identity, PCM, independent acoustic and deliverable A/V checks.

All audit results are recalculated twice without model or audio regeneration
and an immutable SHA-bound
`.microgen_autonomous_acceptance.json` is created only on full technical
success. The batch checkpoint also records a dependency fingerprint of
all code, input evidence and generated output MP4 parts so stale acceptance
cannot be reused after upstream edits.

**No human approvals are gates**, and neither user nor lecturer must intervene
in the normal technical development loop. Equally, this receipt does NOT
certify all scientific claims, every spoken phoneme, protected figure
redistribution rights, pedagogical suitability or element-level synchronised
highlighting. Those remain accurately labelled as not proven.

## Publication separation

`publication_allowed=false` and
`copyright_distribution_authorized=false` are explicit in every acceptance
receipt. Accepting a private video does not copy it to Google Drive, YouTube,
Moodle, a student's device or another distributed destination. The existing
publication operation retains its separate ownership/rights restrictions.
No external upload is carried out by this PR.

## Verification

Automated tests verify that the gate:
- accepts only a complete private source/WAV/video/ASR/scientific evidence set;
- rejects changed WAV/source or unsupported fabricated approval/rights flags;
- refuses missing science or acoustic evidence;
- rejects contradictory two-pass audits; and
- distinguishes technical pass from stronger scholarly/phonetic certification.

A real private Serway Chapter 2.1 media probe confirmed that previously
generated parts of **301.8s and 325.9s** satisfy the strict duration check,
while the absence of full independent acoustic evidence still correctly
blocks technical acceptance. No human approval and no source/MP4 modification
were involved.

A passing technical acceptance must not be inflated into a guarantee of
unobservable mathematical, scientific or pronunciation correctness.
