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

## MG-20261024-004 — different FFmpeg AAC decoders produce nonidentical PCM (HIGH)
- Real Dell-115 source MP4 had 8,820,054 decoded samples on both older
  LAMMPS FFmpeg and imageio 7.1; PCM hashes differed
  (old `21cc4747ef1f748134edee2696ba06cd10ac56fce6e713adbb450068ca79fe7d`
   vs new `f753bfd1dd8573cc3782b5069895b690c5b16d319e41225675e3177a982e8afe`).
  Old decoder had made source-bound recovered scene WAVs.
- v7.1 `tpad` supports final-frame extension; old LAMMPS FFmpeg does NOT.
  First unsupported-filter attempt and subsequent cross-decoder exact-PCM
  integrity gate were correctly blocked, never counted as acceptance.
- PR #180 optional explicit `source_decoder_ffmpeg`: verify untouched
  historical MP4 decodes **sample-equal to the already recovered 17 WAVs
  with the original decoder**; render with a tpad-capable local binary,
  verify the resulting lossless ALAC media independently re-decodes to
  that same exact master PCM. Receipt fingerprints both FFmpeg binaries.
  Preflight tpad before any output. No PCM equality relaxation.
- Real final original-audio technical ALAC 551.25 s with exact samples,
  candidate SHA `ab7fe4120b4f4854471eb83fccc9ab2bc53c4cdd0affa150cdbe9446e39c8943`.
  Pronunciation and release remain UNVERIFIED.

## MG-20261024-005 — cloned 2.5 folder lacks generated files (RESOLVED source discovery)
- A read-only historical production audit found a different protected
  lecture path and validated PDF and MP4 SHA against independent
  October 19 owner promotion evidence.
- PR #180 new fail-closed isolated source snapshot verified 13 exact
  files, recovered 17 scene WAVs and 1.023375-s AAC tail, reviewed four
  historical correction candidates, staged 3 selected trial replacements,
  then generated actual corrected 17-WAV timeline 551.686 s and full
  corrected-shadow PCM 552.709 s. Nothing written to historical G: or
  the source clone. Voice, word alignment and figure semantics unapproved.
- Remaining hard blocker: Dell lacks installed optional Vosk, so real
  corrected word cue re-alignment cannot be certified. Original source
  restoration is not the same as publication-quality lecture completion.

## MG-20261025-006 — corrected 17-slide WAV/PCM lacked inspectable video
- Repro: Real PR #180 produced corrected shadow WAV but not corrected visual candidate, so no media-level PCM verification or reviewer-friendly visual playback.
- Fix: New SHA/source/clip/selection-verified `microgen_corrected_shadow_video.py` renders original PDF-derived lecture picture plus full corrected shadow PCM into an isolated **non-highlighting**, **nonpublishing** ALAC MP4. Demands exact decoded PCM equality, strictly <600 seconds, refuses output overwrite and clears only newly-owned output after failure.
- Dell real case: 552.71-s candidate, all 17 scenes retained with unapproved changed clips 5/6/10, original AAC tail retained. All earlier word cues intentionally excluded. No mathematical/phonetic/listening approval inferred.

## MG-20261025-007 — corrected full shadow video reused old slide boundaries
- Corrected trial segments modify 5/6/10 durations; simply replacing original soundtrack under the 550.23s historical video (PR #181) retained outdated visual slide boundaries.
- PR #182 uses original SHA-bound PDF pages, corrected 17 current WAV measured timeline and AAC tail receipt to render independent full visual sequence with explicit page durations. Real 552.71-s 17-page ALAC candidate, exact PCM equal. It intentionally includes **zero** stale word-level highlights.
- Still unverified: real frame-to-slide pixel mapping and tolerance at 17 boundaries. Must validate independently before accepting corrected slide-level sync.

## MG-20261025-008 — FFconcat sparse-still seeking leaks next slide (HIGH)
- Reproduced on real corrected candidate: 16/17 interior FFmpeg screenshots (seek within active slide interval) resolved to the next PDF page, despite successful audio and duration checks. Sparse VFR timestamp seek not trustworthy for slide-level inspection and timing.
- Fix: output regular 8-fps video frames with explicit `fps=8 -fps_mode cfr` before H.264 encoding. Fresh output verified 17/17 correct current PDF page pixels at interior samples with absolute pixel MAE 0.13–0.40 (320x180 samples). No reused old highlights. Permanent full per-slide/boundary audit remains next milestone.

## MG-20261025-009 — slide-level sync lacked persistent independent frame verification
- QA probe for PR #182 demonstrated 17/17 good interior matches but code did not store systematic bounded after/before boundary checks; sparse VFR predecessor once returned wrong slide at 16/17 samples.
- PR #183 implemented independent source-PDF rerender + 50-sample actual decoded MP4 comparison, conservative pixel error threshold, explicit best-matching PDF page and source hashes in nonpublishing audit receipt, source mutation/false approval rejection, no production overwrite.
- Genuine v2 corrected video 50/50 expected PDF pages matched including 16 transitions sampled on both sides and retained audio tail; 0.35s is a probe guard, not a continuous-time guarantee. Word-level mathematical sync and phonetic acceptance remain blocked.

## MG-20261025-010 — no user-ready exact A/B pronunciation review packet
- Corrected trials (5/6/10) were available, but no integrated source-bound A/B listening packet with current corrected-video technical pixel evidence and original PDF/script.
- PR #184 builds an isolated HTML+CSV+original/trial WAV comparison, checks exact source/scene/trial SHA and prior 50/50 page audit, refuses forged approvals or changed assets. No automatic review verdict.
- Real Dell packet has 3 listening slides/6 WAVs and 3 source PDF previews; pronunciation "c" vs "circa", y-value and speaker identity remain explicitly UNREVIEWED. Publication still blocked.

## MG-20261025-011 — individual corrected media reports lack consolidated fail-closed approval gate
- Prior PRs #181-184 verified real corrected video PCM, PDF slide times, 50 source-frame samples and A/B review artifact, but these do not prove new word-level acoustic alignment or mathematical narration semantics.
- PR #185 creates a corrected-lecture-specific cross-stage SHA audit rejecting forged pixel/PCM/source/voice review evidence. Always outputs release BLOCKED with precise outstanding issues, including missing Vosk/local model, no fresh corrected word cues and no academic/listening approval.
- Real Dell audit: 17 slides, corrected 552.709-second PCM, 50/50 pixel samples; 8 independent blockers and `publication_allowed=false`. No historical G: teaching assets or protected main modified.

## MG-20261025-012 — offline corrected-word ASR blocked by missing model and nonresumable capture (HIGH)
- Initial Dell audit of base Miniconda and three named Conda envs found no Vosk/PocketSphinx, no preverified local model; PR #178's monolithic 17-slide capture would lose successful late-stage work on a transient failure.
- PR #186 introduces an isolated, version-pinned offline Vosk setup with verified public SHA-256 ZIP and **no changes** to protected teaching files, plus per-slide exact source WAV/PDF/script/model hash checkpointing and bounded 1–17 slide resume. If the machine/model/receipt mutates, fail closed; no mismatched old ASR clocks or overwrites.
- Real Dell-115 run: initial three slides then resume remaining fourteen, 17/17 authentic observations, 1,178 words, 1,043 high-confidence words, 66 *new* conservative PDF-word candidate cues SHA `bf5c41dfd2480e1220d03f0f6ddb02640ea1a18b65fd0d532d64108be275832f`.
- Remaining acceptance: these are **model observations**, not phonetic or semantic proof. They have not been rendered as highlighted video or independently pixel/linguistically QA'd. Release blocked.

## MG-20261025-013 — fresh corrected SHA-bound text cues lacked a highlighted real MP4
- Genuine PR #186 verified 17 current WAV ASR observations and 66 new conservative PDF-word cues, but those timestamps had no corrected highlighted video and prior rendered candidate deliberately contained no word boxes.
- PR #187 new isolated renderer requires source-verified current v2 cues, Vosk observation source receipt, corrected 17-slide clock + full PCM shadow and PDF bounding geometry, streams an 8-fps source-PDF frame sequence with **candidate** word overlays and exact ALAC PCM. Real technical video 552.75s under 600; 66 text candidate cues; 384 highlighted frames, decoded PCM byte-identical. Single actual pixel spot-check confirms highlighted region really differs from untouched original slide.
- The video is NOT independently word-verified/academically certified and does NOT auto-release. Next gap: full cue ROI/boundary pixel QA and spoken math/figure semantic acceptance.

## MG-20261025-014 — no comprehensive independent decoded word-highlight timing/pixel audit
- Genuine PR #187 generated 66 source/WAV SHA-bound overlay candidates but a single spot check could not rule out absent, mis-timed or lingering cues.
- PR #188 adds actual encoded-image screenshot audits at every cue center and 8fps guarded post-cue controls, independently rerendered source PDF and source/cue/ASR/shadow PCM fingerprints; reports never authorize academic, voice or publication acceptance.
- Three actual audit revisions retained. Initial 3/132 controls flagged; improved full-frame seek guard left a codec-baseline sample (4.149 ROI MAE), separately verified against unhighlighted 4.078 MAE baseline, not cue persistence. Final threshold 5.0 controls, **66 positive cues +64 control samples accepted, 0 rejected; 2 control slots legitimately unavailable close to slide ends**.
- Does NOT prove phonetic correctness, spoken mathematical/figure content or continuous sub-125ms timing accuracy; media remains nonpublishing.

## MG-20261025-015 — math/figure semantics wrongly conflated with corrected word overlay technical QA (HIGH)
- **Observed:** draft #188 technically passed 66/66 actual corrected PDF text box pixels, but previous 57 math geometry / 34 figure crops derived from historical review could not demonstrate equivalence to NEW corrected WAV/ASR/MP4 lineage. One contextual ASR anchor for maths; 90 other regions lacked even this weak association. Automated pixel success is insufficient for scientific or pedagogy release.
- **Reusable prevention:** new `microgen_corrected_semantic_review.py` requires exact current 17 corrected WAV/model ASR source SHA, 66 fresh cue SHA, complete corrected MP4 SHA/PCM and validated real pixel report; creates all 57 math/34 figure original-PDF crops, 17 playable corrected WAVs, exact slide source script and timestamped ASR, explicit 91-item UNREVIEWED decisions. Conservative two-distinct-unique-word/3s context filter is never a semantic verdict.
- **Real Dell-115:** 17/17 slides, 57/57 math and 34/34 figures inventoried, only 1 textual math hint, 91 review obligations. Source and output SHA receipts stored in isolated Dell AppData, HTML+CSV. No human review, publication prohibited.
- **Status:** evidence-handoff implemented, mathematical/figure/phonetic correctness still **BLOCKED pending independent review**. Test synthetic fixture plus genuine original PDF run, reject missing/changed ASR/cue/audio/PDF/corrected-video/pixel proof and protected tree writes. Follow up by correcting stale release gate reporting and obtaining actual semantic/listening decisions, not inventing approval.

MG-20261025-015 follow-up: reviewer packet v1 asset tampering vulnerability contained permanently by v2 manifest hashing all 130 source-derived output files and fail-closed validator. Real v2 SHA 092939173e4f4118371a0aacf70cb607ebc4c30e513851f922b5fd8d778468ff; 18 new focused tests passed, including tampered HTML/audio/CSV/crops and receipt SHA. Old v1 kept for failure-to-fix history; only v2 use for downstream review. Academic and phonetic QA remain UNREVIEWED.
