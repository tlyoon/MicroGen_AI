# PR225 Serway §1.1 source-to-media handoff

This is an **offline work order**, not a completed lecture or a new TTS default.

The handoff consumes the original four-page Serway source PDF, the independently
verified figure-mapped stage, the eight-page source-excerpt draft, and PR224's
immutable independent fidelity report. It recomputes the PDF/draft audit to
reject tampered or stale evidence. It preserves the original files.

Generate in a **new**, external HP destination:

```powershell
python microgen_serway_handoff.py --stage "<Serway-1.1-mapped-stage>" `
  --draft "<Serway-1.1-eight-slide-draft-folder>" `
  --audit "<PR224-fidelity-report.json>" `
  --new-output "<new-HP-external-narration-work-order.json>"
```

Every draft slide carries source-page identity, a confirmed verbatim excerpt
and relevant SI/figure review requirements. `narration_text: null` is
**intentional**: a short textbook excerpt is not a complete 140–180-word
academic explanation, and the tool may not fabricate a lecture. The output
describes missing source coverage, independent academic/figure checks,
full narration, formal narrator, voice-bound WAVs, MP4 synchronization,
and final autonomous audio/visual quality assurance.

Formal production voice remains **unconfigured** under the owner contract.
Google Cloud TTS remains available only for bounded troubleshooting, never
automatically selected as formal default. No provider is invoked by this tool.
The handoff always records `publication_allowed: false`.

For the original saved HP data, the output is
`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR225_SERWAY_NARRATION_HANDOFF.json`.
The existence of that file neither grants formal voice authority nor
certifies a complete end-to-end lecture.

Next: build the genuinely full source-grounded narration/figure/text layer,
then select an authorized compatible production narrator and verify WAVs,
video and academic consistency before any release.
