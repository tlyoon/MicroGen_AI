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
