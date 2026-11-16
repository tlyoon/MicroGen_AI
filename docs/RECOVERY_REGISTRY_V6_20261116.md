# MicroGen_AI original API — executable recovery registry v6.0

**Host:** HP only for this original API-based MicroGen_AI acceptance campaign. This change does NOT modify the Selenium-based MicroGen_AI_Web project.

## Current independently verified checkpoint

The genuine private Serway 2.7 campaign `20261116_HP_G3_SERWAY27_SOURCE_0F8B_PRIVATE` had 21-slide figure/slide/narration/science and 86-source-cue TTS acceptance but failed independent Gemini acoustic QA. An initial source-blind notation repair reduced historical flags from 14 to 9. Only slide 15 is structurally eligible for a source-blind numerical third-witness mechanism; the source-spoken -32 vs model-heard -3.2 is **not** a harmless numeric discrepancy, and eight further slides are still flagged. The original campaign has exhausted its finite provider scope. No further paid recognition is assumed permitted; G3/G4 have not closed.

## New normal-runner behavior

- Version-controlled `microgen_recovery_registry_v6.json` maintains stable failure identifiers, categories, contextual stage signatures, known production handler, applicability prerequisites, QA verification condition, historical evidence, last validation and finite no-retry policy.
- `microgen_recovery_registry.classify_log_attempt` is invoked by **normal** `microgen_batch.run_subprocess` after actual failed stage output, scoped to the current log attempt. It recognizes only a terminal Python exception with a matching registered stage; PDF/narration text and stale earlier logs are not recognized as live failures.
- A known unresolved acoustic/source/semantic fault is a deterministic scientific QA **hold**; never assume the fix is a source edit, rerun an exhausted provider, or mark QA accepted. The stage's existing recovery handler (e.g., source-exact math planner or independently checked blind-ASR acoustic gate) runs before the classifier. The registry does not permit executing arbitrary code from JSON.
- The driver writes `.microgen_recovery_v6.json` **atomically** on the stage, bound to source PDF SHA, runner SHA and version-controlled registry digest. Only scrubbed rule ID, category, stage, retry/authorization disposition and next safe action are persisted; no raw prompts, private transcriptions, tokens or keys.
- On restart, `process_one` checks `verified_stage_hold` **before** re-executing the stage, including after a crash between durable registry receipt and outer checkpoint. A corrupted/stale/tampered receipt, changed input/code/registry, inconsistent signature or simultaneous conflicting receipt fails closed.
- The normal batch dependency hashes include the V6 policy+code for scientific QA/TTS/acoustic/video/acceptance, so stale QA acceptance cannot be silently retained after a recovery algorithm change.
- A detected scientific QA hold takes precedence over an unrelated Gemini circuit opening. Transient or unknown failures continue under the existing bounded retry/circuit policy, with no implicit new grant. The original stage runner automatically moves to the next stage after a genuinely validated successful stage (the existing executable `STAGES` loop); scientific holds stop that branch, while other independently authorized targets may continue without `--fail-fast`.

## Verification and limits

- Offline replay against the **actual November 16 HP acoustic log** recognized `MGA-20261116-ACOUSTIC-ASR` with `scientific_qa` category and `DETERMINISTIC_HOLD`, without editing WAVs or contacting Gemini.
- Targeted tests cover known history, semantic mapping, unrelated/unknown failures, forged source text, multi-traceback terminal selection, corrupt registry/duplicate signatures, exact source/code/recovery hash, atomic idempotent receipt, crash before outer checkpoint, retry exhaustion, changed scientific input, forged approval, actual subprocess integration, and circuit-vs-QA precedence.
- **Do not infer full v6 readiness** from this registry milestone. End-to-end scenarios involving live API timeouts, an independently developed unknown-failure remedy, concurrent-worker termination, real QA remediation and G3 video acceptance still need separately verified evidence. Passing a synthetic stage or a historical log replay does NOT make the real acoustic stage accepted.
- No new background scheduler/service is created by this change. The existing restarted batch runner can resume at the durable checkpoint and advance without conversation prompts where eligibility and authorization actually exist; it will not act without a running process.

## Recovery policy

New failure classes must first be captured in the persistent checkpoint, classified and verified, then added as **version-controlled registry entries and executable handlers with regression tests**. Update or retire outdated entries and validate environmental applicability before reuse. This is finite, safety-preserving learning, not permission for an LLM to modify paid workloads or scientific standards unreviewed.
