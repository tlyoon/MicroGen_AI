# Source-bound single-cue mathematical-operator recovery

**Project:** original Gemini API MicroGen_AI, **HP only**
**Effective:** 18 November 2026
**Scope:** One genuine, source-timed lecture cue whose mathematical operator is independently disputed. This is NOT a general permission to waive a missing operator, change a mathematical value or publish lecture content.

## Historical failure and root cause

Serway section 2.7, slide 5: original full-slide reviewer A recognized the narration source exactly; reviewer B omitted "divided by", including in a subsequent independent model retake of the identical measured WAV. The earlier separately accepted whole-slide WAV has a **different SHA** from the present four-cue timed WAV and cannot certify it. Slide 7 "multiply by" / "multiplied by" is harmless and is excluded under the current meaning-preserving QA rule. The actual disputed phrase is in source-grounded cue s5_e2. Earlier four-cue revoicing altered unnecessary audio and did not produce independent acoustic acceptance.

## Executable finite recovery

1. Before external calls, compare source PDF SHA, 21 original WAVs, TTS manifest, timed PCM/PDF manifest, 21-slide original two-Gemini failed blind transcripts and prior rejected paid retake in authenticated local private campaigns. Re-evaluate their semantics under the current tested policy. Select exactly one cue containing the original missing mathematical operator, not a guessed slide or timestamp.
2. Reserve one source- and model-bound TTS request **on disk before sending it**. Use one selected Gemini API key, the pinned original TTS model and voice, SDK retry budget one and no fallbacks; candidate audio remains in a separate private work folder. Never reissue a reserved request after crash or model uncertainty.
3. Prepare the replacement **only** for the identified source-attested cue. Preserve all other cue and whole-slide PCM assets unchanged until a valid candidate exists. Concatenate actual ordered PCM without guessed timings, and independently validate every source PDF highlight region, cue SHA, full WAV and measured durations.
4. Reserve separately **one** source-blind recognition request for each of the same two independent Gemini acoustic models. Both actual whole-slide candidate transcripts must preserve the source mathematical operation, numbers, signs and meaning; no manually manufactured audio approval or adjusted WER threshold.
5. Install the exact verified new cue, whole-slide WAV, voice provenance, TTS cache and timed manifest as one crash-safe, SHA-checked transaction. Prove every other slide WAV matches the original authenticated historical source-bound transcripts. Persist a final private receipt that is cryptographically re-validated by ordinary video/acceptance.
6. On a genuine pass, the normal batch runner proceeds to measured highlights, decoded video and private G3/G4 gates; on contrary acoustic evidence, uncertainty, changed source, changed original voice, provider failure, interrupted effect or suspicious asset, stop without any duplicate paid request or silent acceptance.

## Test obligations

Actual 21-slide/88-cue Serway source replay, one-cue fake TTS with independently simulated ASR, deliberate wrong-math recognition, changed/identical PCM rejection, aborted provider effect, stale/malformed cue inputs and transactional no-overwrite recovery. Test outcomes are evidence of code correctness, not proof that generated words were spoken by a real model. Live Gemini and decoded private video acceptance require their own genuine evidence; G3/G4 remain open until then.

**Implementation:** `microgen_source_bound_cue_selection.py`; `microgen_timed_acoustic_repair.py`; `microgen_source_operator_cue_recovery.py`; `microgen_autonomous_acoustic_gate.py`; executable recovery registry v6. Historical evidence remains private; no source book or student artifacts are modified.


## After successful acoustic repair: immutable TTS reuse and checkpoint reconciliation

The actual §2.7 HP recovery repaired one cue, obtained two fresh independent Gemini acoustic passes and correctly replaced five items (one cue WAV, one whole-slide WAV, the slide TTS cache, voice provenance and timed-highlights manifest). It subsequently revealed that the legitimate five new hashes conflict with the **older, still valid pre-repair PCM-reuse inventory**. Merely rewriting this old receipt with new hashes would hide altered assets, and rerunning the old TTS/ASR would duplicate charged work.

The normal-path verifier `microgen_verified_tts_reuse.verify_reuse_receipt` therefore accepts exactly those five differing paths **only after** verifying the unchanged old receipt, every other asset against its original hash, the original WAV/cue hashes in the new paid-request journal, the independent acoustic receipt and both model transcripts, current source mathematics and full measured PCM/PDF timing. It preserves the old receipt bytes.

An interrupted normal batch can retain an `inflight_provider_stage=acoustic_qa` after child QA passed but post-stage validation failed. The `microgen_post_acoustic_reuse_resume` recovery inspects the true old and new Git pins, allows only a narrow verifier/registry/runner change, rechecks science/TTS/acoustic receipts under the new code, atomically rekeys their dependency fingerprints, clears the settled in-flight stage via the existing checkpoint transaction and automatically advances to slide slicing, timed video, sub-600s parts and private acceptance. No new Gemini/TTS call is authorized by this reconciliation. Any source, scientific-reviewer, narrator, TTS producer or unrelated code change denies the migration.


## Original paid campaign consent is not migrated to a new code revision

The bounded campaign authorization is cryptographically bound to its initial code commit. Changing that commit cannot silently extend its paid authorization. For a campaign whose audio and two independent Gemini QA reviews are already accepted, the new `microgen_campaign_authorization._offline_verified_acoustic_continuation` admits **only an offline continuation** with the same exact source, owner, host, model environment, private work root and acceptance endpoint. It authenticates the original checkpoint and source/operator repair with a limited Git verifier-only diff; it returns `offline_continuation_only=True` and leaves the existing grant bytes untouched. The batch runner has an independent executable provider-stage guard that rejects all new Gemini, narration, scientific, acoustic or TTS provider operations under this status; only local rendering, split-video checks and private acceptance may proceed. New paid work still requires a separately authorized campaign.


## 19 November 2026: historic authorization-module SHA reconciliation

An already-verified acoustic repair can be blocked on restart when the original TTS-reuse receipt treats `microgen_campaign_authorization.py` as a TTS producer dependency. The new offline-only consent enforcement necessarily changed that authorization module after genuine narration and TTS creation. The old immutable receipt is correct: it contains the exact SHA of the module in the original pinned HP commit `bcf192d`. Updating its hashes or silently omitting that dependency would conceal an untrusted source change.

`microgen_post_acoustic_reuse_resume.verify_original_authorization_module_delta` now establishes the exceptional, safe code transition by comparing the receipt's original authorization-module SHA with `git show` of the source-bound original owner's commit; verifying the original private host, source, stage, grant and saved acoustic checkpoint; verifying the intermediate checkpoint revision is an ancestor of the new frozen commit and the staged module exactly matches its corresponding Git blob; and enforcing a strict, complete Git diff allowing only the audited recovery/authorization/contract/tests. All other **eleven** original TTS producer policies must still have their original exact hashes. The old TTS receipt, audio and source hashes remain immutable, and the independently accepted two-Gemini recording and five-asset correction are reverified.

A failed restart had already advanced `checkpoint.package_commit` to a later verifier revision while retaining the original paid grant. The normal campaign now retrieves the *original* code revision from the immutable provider authorization rather than treating that overwritten checkpoint field as authoritative. A source, voice, TTS model, mathematical cue, untrusted producer module, unrelated code change, corrupted journal or modified paid grant is still a hard hold. This does not grant any additional billable request; the surviving pipeline is strictly offline/local video, splitting and private acceptance only.


## 19 November 2026: upstream-source receipt reconciliation

The original six/four-stage upstream-import receipt also records the former runner code revision. An earlier failed restart may update `checkpoint.package_commit` even though the original accepted source/slide/narration/physics and model audio are preserved. The standard upstream verifier `microgen_verified_upstream_reuse.verify_import_receipt` therefore accepts a mismatched checkpoint revision **only** after verifying all of its normal source/slides/narration/figure/cached-response provenance, proving the original code revision equals the original owner grant via `verify_original_authorization_module_delta`, and rechecking the independently accepted, source-bound single-cue PCM/audio receipt with `microgen_verified_tts_reuse.verify_reuse_receipt`. An arbitrary different runner commit, source alteration, numerical/math difference, missing transcript, modified Git producer or unapproved code change remains a stop. Both the original upstream-import receipt and the old TTS-reuse receipt remain unchanged; the normal runner can resume the private offline video/split/acceptance gates with zero new model calls.
