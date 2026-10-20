# MicroGen_AI continuation checkpoint — 2026-10-21 (PR #57)

Source of truth: inspect latest LIVE GitHub draft PR stack first. PRs #52–#57 are six stacked DRAFT contributions on #51. Preserve original MicroGen_AI distinct from MicroGen_AI_Web. Work in isolated Dell-115 checkouts; protected main and original lecture media remain untouched. Under October 20 autonomous contract, human listening/academic/figure/highlight sign-offs are OPTIONAL, technical faults and unavailable evidence remain blockers, and every lecture MP4 must be STRICTLY less than 600 seconds with element-level highlighting an ongoing quality objective. No Whisper or external GCS lease.

## Critical real QA finding

The original vs lecturer-corrected Thomas Calculus Section 2.5 slide-10 WAV references are SHA-pinned. 2026-10-20 transcript-only Gemini 3.5/3.8 pair yielded zero scored coverage because model 3.8 failed, while model 3.5 normalized BOTH cases as 'y-value'. A 2026-10-21 direct phoneme contrastive test of Gemini 3.5 and Gemini 3.6 also returned UNKNOWN in all four cases: model pair UNQUALIFIED. Do not claim near-zero or phonetic correctness, even where synthetic unit tests pass. Full raw trial reports remain in Dell-115 temp scratch, not git.

## Latest architecture

#52 script-blind direct audio phoneme probe; #53 live/reference calibration; #54 risk-scoped calibrated slide checks; #55 independent source and claim verification; #56 strict opt-in phoneme check before full ASR with no human gate; #57 selects a candidate pair ONLY after passing real labeled audio benchmark. A passing pair is qualified solely for the tested Y-value risk family, not entire narration, scholarship or visuals. If no pair passes, report NO_QUALIFIED_AUDIO_PAIR instead of silent fallback. Follow-up: search for a genuinely phoneme-sensitive acoustics method, expand confirmed real labeled corpus, improve element-level highlight validation, and safely reconcile the unmerged draft stack before deployment. No production lecture regeneration or Moodle publication has occurred.
