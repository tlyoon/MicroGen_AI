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

## MG-20261024-002 — no positive recovery after revised narration (HIGH)
- **Evidence:** PR #177 correctly blocks v1 cues and changed WAVs, but its usual
  renderer does not regenerate corrected ASR-based clocks. Without a source-
  grounded regeneration step an owner could be tempted to reuse the 66 old
  cues or manually patch clock offsets.
- **Permanent improvement:** PR #178 candidate `microgen_corrected_cue_realign.py`
  provides optional local Vosk capture on the **actual staged WAV bytes**,
  rehashes all audio after the full capture, verifies exact PDF/script/WAV SHA
  and measured duration for each slide, produces conservative PDF-word cues
  and binds v2 timing before a new `cues.json` is created. Existing output
  is never overwritten; release remains false.
- **Regressions:** Nine new pytest cases cover fresh current audio, legitimate
  replacement timeline re-estimation, stale old reports, old format, forged
  certification, missing/misordered slides, invalid word-time/confidence,
  duplicates, collision and mid-ASR alteration of an earlier clip. Dell-115
  full pytest 738 passed/3 skipped; 593 legacy unittest passed/3 skipped.
- **Limits:** PR still draft/unmerged; no actual corrected §2.5 audio ASR
  acceptance measured on Dell; original c./y defects and formula/figure
  semantics remain unresolved. Synthetic ASR mocks are not independent
  phonetic acceptance.
- **Next:** Create isolated corrected 17-WAV workspace with explicitly
  source-verified historical trials, then run capture/align on its actual
  audio (provided local Vosk model exists). Independently review and verify.

## MG-20261024-003 — no source-safe full corrected WAV staging (HIGH)
- **Historical gap:** The recovered legacy source yields 17 provisional scene WAVs,
  and three source-receipt-verified corrected trials exist separately, but there
  was no complete source-verified and reusable corrected 17-WAV workspace with
  a newly measured global timeline. Reusing the 17 original cues risks
  misalignment, and promoting source historical WAVs directly would be unsafe.
- **Permanent implementation in PR #179 draft:** New
  `microgen_corrected_audio_stage.py` requires exactly 17 source verified
  recovered clips and three explicitly selected UNAPPROVED trials (5/6/10).
  Preflights actual hashes, selected paths, risk classes, original source MP4,
  source PDF/script and measured mono PCM16 durations. Creates ONLY a new
  external isolated stage with 17 WAVs, inventory, measured timeline and
  `fresh_offline_recognition_required=true`. Never copies any prior ASR
  cues or modifies originals. All source files and receipt hashes are
  checked again after staged copying; errors remove only the owned new stage.
- **Adversarial regression:** new synthetic 17-slide real WAV fixtures,
  correction duration shifts, tampered trial/recovered audio, duplicated or
  missing trials, forged approved/source status, source video drift, unsafe
  lecture duration, overwrite/protected destination, race during WAV copy
  and selection receipt mutation. Real actual Thomas section 2.5 still
  requires a separate source-verifiable pilot on Dell.
- **Status:** implemented in isolated Dell-115 draft branch, source media and
  protected main untouched; phonetic and full multimedia acceptance remain
  blocked. Do not infer real corrected video or publication from unit tests.
- **Next:** actual stage from real historical §2.5 selections, offline Vosk
  recognition to all current WAVs (PR #178), v2 cues, pixel/audio/semantic QA.
