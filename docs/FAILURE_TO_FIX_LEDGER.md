# MicroGen_AI Failure-to-Fix Ledger — 2026-10-24

Source of truth: `docs/CONTINUATION_CHECKPOINT_LATEST.md` on newest **live draft**. Entries here distinguish permanent code from local containment.

## MG-20261024-001 — stale word cues after voice/WAV replacement (HIGH)
- **Evidence:** PR #162 `microgen_source_safe_orchestrator.render_complete_staged_lesson` formerly checked only `cues.json.version==1` and presence of elements; cue manifest had no per-slide WAV identity or clock binding. PR #169 generated separately resampled correction clips (slides 5/6/10) with different durations and set `all_preexisting_ASR_cue_timing_invalidated=true`. Existing renderer lacked a standalone check against new audio.
- **Classification:** Actual reusable structural integrity weakness; corrected full-lecture render not yet attempted with such stale cues. No claim of observed accidental publication. Transaction state: code **not submitted/used** for a corrected production video; older original candidate complete and staged.
- **Permanent fix:** PR #177 `microgen_audio_cue_binding.py` replaces unbound v1 cues in both normal entry points with v2. At pre-render it re-hashes every actual slide WAV, checks inventory SHA, measured timeline/duration, cue absolute/local clock, source PDF and geometry; refuses preexisting v1 and mismatched correction audio before writing video outputs. Fail-closed; no Whisper or paid service.
- **Adversarial regressions:** Actual synthetic replacement WAV SHA and duration with updated inventory/timeline while stale cue binding persisted; raw WAV byte corruption; old v1; wrong absolute cue clock; out-of-page PDF box. Expected rejection. Real read-only §2.5 check: 17 WAVs and 66 original cues accepted after binding; slide-6 historical corrected trial hash substitution rejected, moved word clock rejected.
- **State:** IMPLEMENTED IN DRAFT, pending hosted CI/merge; acoustic phonetic truth and corrected render remain blocked.
- **Next:** Source-hash and re-recognize the corrected WAVs, derive *new* v2 cues; run a full nonpublishing corrected render and sample frame pixels.

## MG-20261019-CDOT — “c.” spoken as “circa” (HIGH)
- Three source-bound original slide-6 Vosk 'circa' detections; corrected trials for slides 5/6 stage separately. Voice provenance is only a provider-name claim; ASR confidence is not listening proof.
- State: SAFELY CONTAINED, not independently resolved. Next: acoustically verify corrections and speaker consistency before replacing production track.

## MG-20261024-SHADOW-VOICE — 6 pronounced volume joins / speaker unknown (MEDIUM)
- 16 join windows analyzed on corrected shadow WAV; six above 8 dB RMS difference. Loudness is not a speaker-identity test.
- State: DIAGNOSTIC ONLY; requires acoustic review and full corrected video re-timing.

## MG-20261024-MATH-SYNC — incomplete equation/figure highlighting (HIGH)
- 57 source-PDF math-line candidates, 34 figure candidates, one conservative matching contextual phrase. 66/66 selected text overlays visibly appear but cannot establish meaningful semantic element timing.
- State: BLOCKED by missing source-grounded semantic mapping and academic acceptance. Do not fabricate timestamps; keep publication false.

## MG-20261024-AUDIO-TAIL — historic decoded AAC overhang (RESOLVED technical)
- Historic 17-slice WAVs omitted 1.023375 s; PR #163 used exact decoded PCM source equality and held final frame; PR #166 converted to common H.264/AAC format after lossless QA.
- State: RESOLVED FOR ORIGINAL historical soundtrack, not asserted for corrected shadow. Retain failure and tests, check all future replacements.

## MG-20261024-PROVIDER — transient/billing UI/provider failures (HISTORICAL)
- Older simulated tests exercise fake Gemini billing/transient errors. No fresh provider outage diagnosed here, no new requests sent.
- State: Not relevant to this offline PR; general recovery must retain billing circuit breaker, retry/receipt distinctions and no implicit paid calls.
