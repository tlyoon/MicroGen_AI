# MicroGen_AI — Release Closure Development Contract

**Version:** 1.2 · **Effective:** 7 November 2026 (Asia/Kuala_Lumpur)
**Project:** original Gemini-API `tlyoon/MicroGen_AI`, not Selenium `MicroGen_AI_Web`.
**Mode:** RELEASE CLOSURE (default for all subsequent project-development invocations).

**Owner amendment (12 November 2026):** Standing autonomous HP private G2/TTS
development authorization, contract version **1.1**. This amendment governs
conflicting earlier statements requiring renewed human approval for ordinary
private content/TTS generation. It does not grant publication rights or
unlimited paid provider usage.

**Owner amendment (13 November 2026):** Contract version **1.2**
makes **automatic recovery in the normal pipeline** a mandatory, testable
development requirement. It strengthens the autonomous progression rule without
expanding provider spending, device scope, publication authority, or QA waivers.

## 1. Authority, precedence, and objective

This is the **controlling forward-development and closure procedure** for
MicroGen_AI. Read it first, together with
`AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md`,
`AUTONOMOUS_PRIVATE_RELEASE_ACCEPTANCE.md` and
`TIMED_ACTIVE_HIGHLIGHT_CONTRACT.md`.

It **supersedes older procedures** where they demand unrestricted iterative
enhancement, repeated PDF-specific repair, PR-count targets, obsolete device
assignments, or human sign-off as a prerequisite to technical progression.
It **does not supersede or weaken any substantive safety, scientific,
acoustic, semantic, provenance, visual, copyright, monetary, or release gate**.
Later explicit owner instructions prevail within their authorized scope.
Historical results stay available as evidence but cannot substitute for
acceptance on the current frozen code and new real inputs.

**Finish the complete private lecture-generation product, then freeze.**
Success is a reproducible source-PDF-to-accepted-private-video workflow,
not an ever-growing quantity of code, checks, PRs, or repair attempts.

### Mandatory automatic recovery and forward progression (13 November 2026, v1.2)

**Binding principle (verbatim):**

> Automatic recovery must be part of normal pipeline execution, not depend on
> the owner repeatedly asking the developer to fix the next blocker.

This is a **release-closure development requirement**, not an aspiration or
an instruction applicable only to a particular PDF. Every future code change,
G2/G3 campaign, resumed session, and new recovery implementation MUST follow
this policy. The developer MUST inspect earlier commits, failure records, test
fixtures, recovery receipts and previously implemented repair mechanisms before
treating a familiar blocker as an unsolved case. Search only the **original
Gemini-API MicroGen_AI** history, not the Selenium MicroGen_AI_Web project,
unless the owner explicitly authorizes a cross-project comparison.

**Normal-pipeline recovery contract:**

1. **Identify and classify the failure automatically** at the stage where it
   occurs, preserving its source/code/input SHA256, affected stage and
   independent evidence. Distinguish deterministic known defects, transient
   provider failures, untrusted QA observations, missing prerequisites,
   genuinely changed input/audio, and failures requiring new authority.
2. **Reuse verified historical remedies automatically.** Connect the remedy to
   the ordinary production entrypoint (`microgen_batch.py` and its actual
   stage modules), rather than relying on a standalone troubleshooting script,
   conversation memory or a manual patch. Remedies must be source- and
   version-bound, finite, safe to repeat, and compatible with resumed runs.
3. **Revalidate after each repair.** Require applicable regression tests and
   actual stage-specific quality/provenance checks. A successful recovery must
   produce an explicit SHA-bound result/receipt and restore the normal
   checkpoint state. A previous blocked receipt, model output or WAV is never
   silently converted into a passing QA result.
4. **Automatically continue downstream.** After an independently verified
   repair, the SAME normal runner proceeds to the next eligible stage without
   owner prompting or redundant manual approval. In particular, successful
   acoustic QA must trigger slide slicing, synchronized video generation,
   strict per-video duration checks (each less than 600 seconds), decoded
   visual/source verification and private final acceptance under the same
   authorized finite campaign. Do not stop merely to report that a familiar
   blocker has been resolved.
5. **Preserve all unaffected verified work.** Use exact dependency
   fingerprints/checkpoints to reuse figures, slides, narration, scientific
   reviews, source-grounded cue plans, and original PCM when still valid.
   Invalidate only the changed inputs and their true dependents. An
   acoustic-review-only change does not justify resynthesizing byte-identical,
   source/voice-proven WAVs; a real voice-input change DOES invalidate those
   WAVs and requires new acoustic/synchronization evidence.
6. **Generalize any newly discovered remedy.** If an earlier remedy does not
   exist, reproduce and classify the actual new failure; implement the
   smallest general-purpose recovery in the codebase, add positive and
   adversarial historical-failure replay tests, and integrate it with the
   production stage and dependency fingerprints. Once genuinely verified,
   future instances of the same recoverable failure must use it by default.
   No one-off per-slide workaround qualifies as closure.
7. **Prevent repeated failure loops.** Use finite retries and repair budgets,
   idempotent or transactional writes, strict stop conditions and deduplicated
   source/code/provider fingerprints. Do not endlessly retry one PDF, reset a
   consumed paid grant, regenerate unchanged inputs, fabricate evidence or
   lower a mathematical/acoustic/visual acceptance threshold merely to move
   forward.

**Exception, not a loophole:** Automatic recovery cannot guarantee that
every future defect is solvable. Unknown failures, contradictory independent
scientific/acoustic evidence, unavailable providers, unsafe or corrupted
source data, exhausted finite authorizations and unapproved publication MUST
remain explicit fail-closed holds. Record a typed, actionable root cause and
the next safe action; keep progressing with any *independently authorized*
work. Do not treat a hold as successful completion or repeatedly request
routine manual approval. A new paid campaign, new provider/source scope or
irreversible release still requires its legitimate authorization.

**Mandatory development acceptance evidence:** For every blocker-recovery PR
or patch, document (a) the historical failure and its generalized class,
(b) where automatic detection/recovery is called in the real runner,
(c) a replay of the original failure and negative counterexamples,
(d) proof of existing-asset integrity and finite retry/rollback behavior,
(e) successful resumption to the next stage when the recovered output is
valid, and (f) any honestly remaining unresolved gate. Unit-test success or
a ChatGPT claim alone does not establish real G2/G3 video acceptance.
The release-closure contract itself and the README must remain visible
entrypoints for future development sessions.

### Standing autonomous development and bounded campaign continuation (10 November 2026)

**No repeated manual approvals for ordinary development.** In the authorized
HP Windows/API worktree, execute routine reversible code changes, checks,
source-free validation, regression tests, permitted AI-based academic/technical
QA and previously approved bounded recovery automatically. Do not ask for
human approval of each stage, familiar repair, automated QA result, checkpoint
resume or ordinary implementation step. Keep advancing through all stages
*within the same finite previously authorized private campaign*. Any
generalizable remediation must be invoked by the normal production caller,
protected by historical-failure replay tests, and preserved in the codebase.

The normal `microgen_batch.py` entrypoint now calls
`microgen_campaign_authorization.authorize_or_resume` for a **single-target,
bounded, private provider campaign**. Its first launch records the existing
explicit provider authorization in a private, exclusive local receipt
`.microgen_bounded_provider_authorization.json`; later identical resumptions
reuse that verified receipt **without repeating an approval flag or asking the
owner**. The receipt binds the original source SHA256, exact code SHA, private
host/paths, fixed endpoint stage, voice/model/environment choices, multipart
mode, and maximum stage-retry count. The procedure refuses changed source,
runner, provider, voice, elevated retry allowance or stage scope, malformed
authorization, an unchanged prior terminal stage failure, or a publication
request. The existing within-process bounded retries and API key rotation are
unchanged; no unapproved second source, changed provider or restarted spent
campaign is inferred. Existing unbounded production/explicit publication
permissions remain separate. Do not retroactively assume a previous
figure-mapping-only authorization also covers new paid slides or TTS.

**Ambiguous-send crash protection:** For this scoped autonomous mode, before
launching any provider-bearing child stage, the normal batch runner atomically
records `inflight_provider_stage` with stage name, source SHA and code SHA
in the existing checkpoint. A verified successful completion clears that
marker in the same checkpoint save. An interrupted stage with an uncertain
model/TTS call cannot be replayed on the next invocation merely because the
original process died or a new chat began; it must fail closed and preserve
evidence. An independently verified existing science-QA result may be
recovered without a new Send, using its original source-bound receipt.
Known transient failures are automatically handled within the original
single run and its already permitted key rotation/retry budget. This adds
**no human approval gate** and does not mistake a safe stop for recovery.

**Approval boundary is about substantive new authority, not routine work:**
a newly billed source/provider/campaign beyond an existing permitted scope,
external publication, destructive overwrite or rights/security override cannot
be authorized by a generic development prompt or silently expanded. In that
case the automation must stop the *restricted operation*, preserve its evidence
and continue any independently authorized work; it should not repeatedly ask
for the same routine approval. A safe stop is not a successful full lecture.

## 2. Nonnegotiable operating constraints

- **Device isolation:** original MicroGen_AI development, real-media production,
  local QA and validation run on **HP only**. Dell-115 is for MicroGen_AI_Web;
  do not transfer these two repositories' runtime, contracts or machine rules.
  GitHub-hosted CI is allowed **on Windows runners only**. Windows is the sole
  supported development, validation and execution platform; Linux/Ubuntu and
  macOS are explicitly out of scope. Neither an Ubuntu/Linux CI result nor
  compatibility with those platforms is a release acceptance requirement.
  Do not use Yoga6/Zenbook for this work. The older Dell-only statements in
  historical contracts/issues are obsolete.
- **CI contract:** the sole required hosted acceptance matrix is **Windows-latest
  with Python 3.11 and 3.12** (two jobs). The Windows-only CI validator must
  reject missing, failed, duplicate or non-Windows jobs. Historical 4-job
  Windows/Ubuntu evidence is archival and not a new mandatory requirement.
- **Architecture:** existing Python + Gemini API design; reuse rather than
  replace working modules. No local language models, Whisper, or unsolicited
  migration to a different agent/browser/provider system.
- **TTS:** Gemini 3.8 Flash-Lite with Kore remains the primary authorized
  lecture-TTS choice; same speaker/provider across each complete generated
  lesson, with the established Gemini Flash fallback. Preserve all formal
  provider-authorization and cost preflights. Google Cloud TTS is only a
  separately scoped troubleshooting path or the owner's standing finite
  last-resort fallback **after both Gemini 3.8 TTS choices fail**; never the
  formal default, never an unbudgeted or mixed-provider lecture.
- **Cost/privacy:** keep source PDFs and generated textbook media private,
  do not expose credentials, never commit private content. Restrict billable
  work to existing authorization and explicit bounded case/request budgets;
  never use unlimited model retries or silently expand the trial set.
- **Technical QA:** retain scientific source grounding, figure lineage,
  correct narration and mathematics, pronunciation evidence, same-voice
  source/WAV hashes, PCM integrity, monotonic measured cue timing,
  synchronized active-element visual checks, and FFmpeg audio/video
  verification. Each **delivered** MP4 part must be strictly below 600 s;
  the private internal combined archive may exceed it if the established
  parts contract permits.
- **Honest claims:** autonomous technical QA requires no routine human
  academic/listening approval to advance development, but machine evidence
  cannot certify unobservable scientific meaning or phonemes. Mark unverified
  dimensions explicitly. Never transform an advisory into a silent pass.
- **Publication boundary:** technical acceptance grants no redistribution,
  YouTube/Moodle/Drive upload or copyright rights. External publication is a
  distinct, explicitly authorized phase.

## 3. Frozen v1 deliverable and four release gates

No new capability may be added to v1 unless a reproducible, generalized
failure proves it is indispensable to one of these gates.

| Gate | Acceptance condition | Required evidence |
|---|---|---|
| **G1 — Code integration** | Required modules and approved PRs (including pending semantic-cue work, if validated) are integrated into one coherent pinned main/release candidate. No duplicate implementations, uncommitted production changes or obsolete provider/device settings. | Exact Git SHA, main/PR comparison, focused and repository-wide regression results, hosted **Windows-only** CI result (supported Python versions) or explicitly documented CI unavailability; Ubuntu/Linux CI is never a blocker. |
| **G2 — Fresh full lecture** | A newly generated **real-source** textbook subsection proceeds through source/figure extraction, mappings, slides, science-grounded narration, authorized Gemini Flash-Lite TTS, independent acoustic QA, measured element highlighting, video, and autonomous private acceptance. The output is not a historical reconstructed/static lesson. | Full stage checkpoint; verified original source hashes; receipts for science, figures, audio/voice, acoustic, decoded visual cues and A/V; all parts <600 s where applicable; final private acceptance receipt. |
| **G3 — Repeatability and recovery** | Two **additional, distinct real-source subsections** pass the same mandatory acceptance, without per-PDF code tailoring. Include at least one genuinely long (>=600 s combined) source-bound candidate with verified sub-600 s parts, and one bounded interruption/resume/fault-injection proof of transaction recovery on real media. | 3/3 independent section pass/fail matrix and SHA-bound receipts, stage histories, timing/part evidence, proven no-overwrite rollback/resume. |
| **G4 — Freeze and private release** | No release-critical failures remain; versioned code and frozen default settings pass repeatable offline/CI and real-case checks, and the owner-independent private technical release is reproducible on HP. | Final acceptance matrix against a pinned commit, failure ledger, release tag/version, runbook, private artifacts, and a closed release tracker. No claim of public distribution approval. |

A gate is **PASS** only on actual evidence for the stated criterion.
`PARTIAL`, `BLOCKED`, `DEFERRED`, and `UNVERIFIED` are not PASS. A
successful local test, PR, or previously accepted static video does not
advance G2/G3 automatically. A gate may remain blocked while independent
work on other gates proceeds; G4 cannot pass if any mandatory gate is blocked.

## 4. Mandatory decision loop for every development invocation

1. **Refresh actual truth first.** Identify original MicroGen_AI, the
   authoritative owner policy, correct HP checkout, local dirty work, pinned
   branch, current GitHub main/PRs and latest release issue/checkpoint. Compare
   live GitHub main before declaring any feature missing; a stale
   `origin/main` or prior chat is never authoritative. Preserve the user's
   changes and old failure evidence. Do not alter MicroGen_AI_Web.
2. **Evaluate the whole release**, reporting G1-G4 PASS/PARTIAL/BLOCKED and
   their exact receipt/commit evidence. Select the earliest unresolved
   *critical-path* dependency, not the latest interesting PDF defect.
3. **Prioritize one highest-leverage intervention** (at most three substantial
   priorities per invocation). State the gate it advances, deterministic
   acceptance criterion and whether real execution is possible. Avoid
   preemptive enhancements, new QA frameworks, excessive docs and parallel
   competing recovery systems.
4. **Investigate the existing implementation and historical signature**
   before modifying code. Check prior commits, PRs, failure ledger, QA
   exemptions, stage checkpoint, provider health, compiler logs and actual
   source state. If already fixed, test its integration instead of redoing it.
5. **Apply the smallest generalized fix**, using the established pipeline;
   add a focused regression test and test representative independent inputs.
   Do not repeatedly alter one subsection until it looks good.
6. **Run bounded validation**: static checks -> targeted tests -> relevant
   integration tests -> one authorized real-source probe -> full gate
   acceptance when warranted. Record exact exit codes, hashes and evidence;
   do not claim hosted CI or live-media acceptance from mocks.
7. **Integrate carefully**: reuse an active relevant PR if available; only
   open a new one if a genuinely distinct gate-level change is justified.
   Never merge a feature whose required tests or source-bound acceptance are
   still unverified. Maintain one version-pinned release candidate.
8. **Reassess G1-G4 and record a continuation checkpoint** for the next
   invocation. Update the existing GitHub issue #278 as the sole release
   tracker rather than repeatedly creating new tracker documents.

## 5. Finite retries and no-repeated-fix loop

- Preserve the repository's existing **bounded** per-stage retry limits,
  backoff and key rotation. Count attempts against the recorded failure
  signature across chat invocations; never restart the limit merely because
  a new conversation begins.
- Group failures by **root mechanism**, not PDF name: source/copyright,
  scientific/semantic, LaTeX, figure geometry, TTS/voice, independent
  acoustic evidence, visual/FFmpeg, dependency/runtime, Git/CI, or external
  Gemini service/auth/billing. A new source is not a new defect if the
  failure signature and implementation are unchanged.
- For the same unchanged code + input + environment + signature, do **not**
  retry the same operation again. Reopen only after new root-cause evidence,
  a meaningful implementation change, a changed external-service condition,
  or a justified independent recovery opportunity.
- During closure, normally permit **at most one general-purpose code
  correction campaign per distinct root cause** before pausing that issue,
  recording precise diagnostics and considering a different independent
  acceptance case. Do not accumulate serial speculative patches.
- Distinguish Gemini HTTP 503/504, quota and auth failures from model-output
  errors, local LaTeX issues, acoustic false positives and browser automation.
  This API-based project has no Selenium-login diagnostic path.
- If a mandatory gate is blocked after bounded recovery, mark it BLOCKED
  with evidence and a minimal actionable dependency; keep other gates moving
  where safe. Never waive science, pronunciation, integrity or copyright
  checks to manufacture progress.

### Permanent known-blocker recovery policy (8 November 2026)

A historical incident or a ChatGPT discussion is **not** an executable
recovery. Mark a known blocker as permanently prevented only when its
production path reproduces the failure under an offline regression and
enforces the bounded corrective behavior under Windows CI.

Reuse the existing `gemini_keys.py` failover and `microgen_batch.py`
checkpoint/driver; do not install a competing self-modifying agent:

- **503/504 recovery:** the configured same-key retry budget and transient
  rotation threshold must be jointly consistent. Zero same-key retries
  allows **one request on each authorized configured key**, not unlimited
  retries and not a premature failure before key #2. The provider's
  billing-circuit and authorization policy remain unchanged.
- **Deterministic source/semantic rejection:** if a child stage exits with
  an independently recognizable source-cue, pronunciation preflight, or
  timed highlight contract error, do not replay unchanged inputs merely
  to consume `--stage-retries`. Persist a `DETERMINISTIC_HOLD` only when
  a complete relevant dependency fingerprint and batch-runner code hash
  can be recorded. On resume, skip an identical rejected stage before
  any model request; a changed relevant code/input or newly authorized
  timed semantic budget releases the hold.
- **Unknown or transient failure:** retain the existing finite retry/
  checkpoint process; unknown causes must never be silently declared
  recovered. Ignore old error lines when classifying a new attempt.
- **Legacy compatibility:** a timed semantic budget change must not
  invalidate an unrelated accepted static-TTS dependency fingerprint.
  Never change previous source, accepted WAV, or MP4 artifacts to force
  recovery.
- **Required replay evidence:** before integrating a recovery change,
  verify at least real historical 503/504 key-rotation configuration,
  safe stopping when all keys fail, deterministic source/QC non-retry,
  checkpoint hold on unchanged inputs, release after genuine input/code
  changes, and a preserved unknown-transient retry path.

This mechanism is bounded orchestration, not a promise that a novel
scientific/semantic failure or general provider outage can be repaired
autonomously. It does not change the requirement for actual G2/G3
real-lecture acceptance or grant publication rights.

**10 November 2026 mixed acoustic recovery contract (Serway §2.5 replay):**
The normal `microgen_autonomous_acoustic_gate.py` must classify
source pronunciation risks, recognizer disagreements, unavailable
transcription, eligible two-slide same-voice TTS repair and other ambiguous
evidence **before counting repairable defects or calling TTS**. Never
describe all flagged slides as confirmed speech errors. Distinct reviewer
disagreements and mathematical-letter source risks must retain the
independent acoustic hold; do not promote a screen pass to proved phonetics,
relax scientific criteria or expand the two-slide repair ceiling.
The canonical stage must preserve sanitized, SHA-bound category receipts
without private script/transcript excerpts. A repeated direct CLI or batch
run with an unchanged WAV/TTS-source snapshot and the same Gemini reviewers
must stop before any new model request; a new process or chat is not a
new cost allowance. The standalone source-attested `x axis` and `x of t`
forms have conservative TTS-only letter-name expansions in
`text_to_speech_v25.py` and matching risk classifications; regenerated
WAVs **still need independent review**. Original §2.5 WAVs, previous
failed review and the spent provider campaign remain preserved. These rules
must be exercised by source-free regression tests and normal entrypoints,
not just incident notes or standalone repair scripts.

**10 November 2026 private acceptance timed-cue cost preflight:** The
real HP Serway §2.5 17-slide deck exposed a separate G2 blocker during an
offline shadow preflight: pure lexical cues cannot ground slide 1, and the
independently counted semantic-assisted slides were
`[1,2,4,10,11,13,14,15,16,17]`, **10 required versus the
pre-existing maximum 4**. This is not a Gemini outage and cannot be
repaired by retrying a WAV or increasing budget without a newly bounded
campaign. The previous TTS path treated measured highlighting as opt-in,
letting a source-to-acceptance campaign pay for unmeasured static audio that
can never satisfy G2's mandatory synchronized active highlighting.

For private `microgen_batch.py --stop-after acceptance` campaigns,
the **normal batch runner** now mandates `MICROGEN_TIMED_CUES=1`
before freezing provider scope. Once slide and narration evidence exists,
it runs the canonical offline `prepare_slide_pages` and
`propose_plan` / `_require_budget_preflight` admission **before**
both paid scientific QA and TTS (or at TTS if scientific QA was previously
verified). A verified existing plan is reused without transcription or
invented mapping. Unsupported lexical grounding or insufficient configured
semantic budget stops that specific stage with an exact diagnostic,
preserving originals; no Gemini request is made in the preflight. This
extends mandatory private G2 acceptance only; previous explicitly
non-acceptance/static teaching workflows retain their existing option.
Do not silently raise the 4-slide budget, fabricate cue coordinates, or
claim timed visual acceptance from this preflight alone.

## 6. Change-control and scope freeze

A proposed enhancement is admissible only if the release tracker records:
**gate**, **reproducible general defect**, **historical solution checked**,
**minimal change**, **test**, and **effect on the G1-G4 pass matrix**.
Reject tweaks that merely improve one PDF, add another unevaluated QA layer,
optimize unmeasured performance, or require a new model/provider without a
release-critical dependency. Do not turn hypothetical perfection into a v1
requirement.

The release candidate freezes as soon as G1 is ready. Later fixes must
identify the exact failing release gate and demonstrate that they do not
invalidate previously accepted receipts; when code, text, voice, WAV or
rendering changes, recalculate only the legitimately affected evidence via
existing dependency fingerprints. Preserve all old assets and rollback
checkpoints. Avoid blanket regeneration.

**Meaning of 'close the codebase':** private v1 is technically accepted
against G1-G4 and tagged; it remains maintainable and may receive separately
scoped v1.x corrections. This is **not** a claim of universal physical
correctness, every mathematical expression's independent semantic proof,
a human-certified pronunciation review, or unrestricted copyright release.
Requirements not machine-verifiable must be disclosed, never disguised as
verified. Any **mandatory** unresolved requirement blocks v1 technical
acceptance; nonmandatory enhancements are moved to a later version, with
their scope kept distinct.

## 7. Mandatory concise release tracker record

Maintain one record in issue #278 with:

- **Pinned release SHA / PRs / HP-only device and frozen v1 scope**.
- **G1–G4:** status, exact acceptance evidence location, last verified date,
  and impact of new changes.
- **Failure ledger:** signature; category; affected workflow; prior
  matching fixes; retries already consumed; root cause; next authorized
  action or terminal disposition.
- **Last three distinct real-source cases:** source SHA (private path or
  private receipt reference, no textbook contents), full stage outcomes,
  acoustic/science/timed visual and video receipts, sub-600 s parts.
- **Open dependencies, restricted actions, next smallest critical-path
  task**, and publication authorization separately.
- **Evidence quality:** explicitly distinguish `PASS`, `PARTIAL`,
  `BLOCKED`, `DEFERRED`, `UNVERIFIED`, and `OUT_OF_SCOPE`.

On every future user instruction to 'proceed', perform the decision loop
against this record and the latest live code. One session's end is not an
authorization to work asynchronously. Do not ask the owner to repeat
previously answered questions; request new permission only for a genuinely
unapproved destructive, security-sensitive, expensive or external action.

## 8. Immediate checkpoint at contract adoption (7 November 2026)

- Live `main` checked at `6567c22`; HP checkout matched GitHub.
- Draft semantic-cue PR #291 (`3c0e56a`) is **unmerged**. Offline full
  unittest run: 937 tests, nine skipped, zero failures. One bounded live
  semantic proposal matched a source PDF block and left inputs unchanged;
  neither result is full source-to-video acceptance.
- Existing Serway 2.1 static 19-slide delivery receipt verifies ordered
  parts of 301.8s and 325.9s. No timed element-level acceptance follows.
- Historical Serway 2.2 stopped at LaTeX slide generation; 2.3 stopped
  at acoustic QA after successful Flash-Lite TTS. Do not retry unchanged
  runs without new causal evidence.
- **Gate statuses at adoption:** G1 PARTIAL (draft unmerged, CI not
  verified); G2 BLOCKED/UNVERIFIED (fresh accepted timed-source workflow
  absent); G3 NOT VERIFIED (three independently accepted sections and
  real interruption/recovery absent); G4 NOT READY. This is a finite release
  campaign, not evidence that the product has already shipped.

## 9. Governing completion principle

**First close the next real release gate. Stop repeating the fix.**
Any future procedural amendment must state which prior rule it replaces,
why the old rule caused a verified failure, and how the new procedure
prevents recurrence without weakening the substantive quality contract.


### 11 November 2026 — reusable source-grounding and acoustic drift prevention

In the **normal** narration path (`gen_script_v13.py`), the model is required
to retain verifiable distinctive on-slide terms, exact title/section names,
mathematical signs, and source meaning rather than replacing every visible
anchor with free paraphrase. This is a preventive instruction, **not** a
semantic proof; the pre-existing `microgen_timed_cue_planner.py` full-deck
offline admission remains authoritative. The conservative lexical matcher may
now ground a *single visible text block* with only one salient term **only**
when its entire text appears verbatim in the spoken cue and every spoken
number is visible; neither sparse multi-block paraphrases nor new numerical
claims are admitted. Unresolved cues stay unresolved: do not raise the
four-slide semantic budget merely to pass this example.

The normal independent acoustic comparison treats the explicit math-coordinate
forms `x of t`/`ex of tee` (and `y of t`/`why of tee`) as equivalent
spellings of the **same spoken letter-name phrase only in this precise
context**. It must continue to flag `yay` for Y, `circa` for C, altered
mathematical sign/value, or unresolvable recognizer disagreement. No ASR
homophone equivalence constitutes proof of phonetic accuracy or overrides a
source-derived pronunciation risk.

Before any new recognition call, the normal acoustic entrypoint checks the
previous signed WAV/voice manifest against the **current normalized speech
inputs**. If speech normalization changed, it reports exact affected slide
numbers only after independently checking every historical WAV SHA and PCM
metadata and enforcing one pinned voice. The unmodified WAVs are left intact.
The report **does not authorize re-synthesis, revalidate the old WAVs, or
mark the acoustic gate passed**. A later authorized finite campaign must
regenerate changed speech in the original engine/voice, preserve unaffected
signed audio, run valid independent acoustic review, and promote nothing on
unresolved risk. TTS/acoustic checkpoint fingerprints include normalizer,
cue-planner and TTS-provenance implementation changes.

**Verified historical evidence on HP, source kept private:** 17 original
Serway §2.5 WAVs structurally usable; signed normalized input has drifted
only for slides **10 and 17**. Fifteen other signed inputs are unchanged.
The full-lecture cue budget preflight went from 6 semantically assisted slides
to **5** using strict full-title evidence, still exceeding the authorized
limit 4: `[2,4,11,13,14]`. Original acoustic review also holds slides
`[10,11,12,13,14,17]`; these are *not* six proven audio defects. No paid
semantic/TTS/ASR request, old-WAV replacement, copyright publication or G2
acceptance was made by this offline development campaign. Keep the
independent acoustic and complete real-media G2 gates blocked until their
actual private SHA-bound receipts exist.


### 11 November 2026 — G2 narration-cache recurrence fix (v5.0)

**Reproduced critical shared integration fault:** The normal
`gen_script_v13.main` previously passed only the external
`gen_script_prompt_v8_hybrid.md` SHA to
`microgen_narration_batch.generate_batched`. The real request also includes
source-anchoring instructions embedded in the Python generator. Changing
those instructions therefore failed to invalidate accepted batch caches.
Read-only HP replay against the actual Serway §2.5 historical 17-slide
candidate showed **all three** `batch_0000/0008/0016.json` caches matched
the legacy key, even with the new source-grounding code. Merely rerunning
narration would have reused old scripts.

**Reusable production resolution:** The active v13 generator now supplies
a per-batch SHA of its **complete composed request**, actual generator
source bytes, model and thinking settings to the shared batch helper.
Changes to the in-code prompt, template, visible slide content, source
context, figure inventory, or generator implementation invalidate
previously accepted cached narrations. Unchanged source/prompt resumes the
old matching result without a Gemini call; the batch helper preserves
legacy caller compatibility. Normal narration dependency fingerprints
also track the shared `microgen_narration_batch.py` implementation when
staged, so a changed cache gateway cannot retain an older completed stage.

**Independent proof boundaries:** Source-free normal-entrypoint tests
verify cached repeat, changed in-code instruction, thinking-setting change,
invalid fingerprint fail-closed, and shared-helper checkpoint invalidation.
The *real private 17-slide cache replay* was read-only: under the corrected
key **zero** of the three old batches is eligible for reuse. This closes
the stale-cache engineering blocker but **does not itself generate fresh
lecture narration**, consume or renew an exhausted provider allowance,
resolve the remaining five semantic cues, repair any old WAV, clear
independent academic/acoustic review, or approve G2/release. A fresh
finite explicitly eligible provider request and original-source
acceptance evidence remain mandatory. No original private source,
narration or audio is modified by this offline proof.


### 11 November 2026 — new G2 real-source attempt and semantic numeric-evidence fail-closed remedy

**Actual newly authorized scope:** A single fresh, private, HP-only Serway
section 2.5 campaign, source SHA256
`923c1768656433f29ba3a2ba413ea81eb5db9383f81d25873358b58709ae14aa`,
run from exact tested code SHA `5b5b1a28d2cfaa43a72c2509d0e05c7d57d217a1`
in `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261111_HP_G2_SOURCE_ANCHORED_PRIVATE`.
Frozen `--stop-after acceptance`, one subchapter, `--stage-retries 0`,
`MICROGEN_TIMED_CUES=1`, semantic assistance budget **4 slides**, Gemini
formal TTS, no Cloud fallback, no publication. Its new, exclusive authorization
receipt remains frozen. The prior spent November 10 provider campaign, old
WAVs, and terminal acoustic marker were not replaced or restarted.

**Source-backed stage outcomes:** Real source extraction, figure mapping,
figure merge, freshly generated slides, freshly generated 17-slide narration
and independent scientific QA **PASS**. The preflight initially admitted
the new narration under four semantically assisted slides
`[11,13,14,15]`; the source science receipt passed. A Gemini 504 during
slides was handled inside the already-integrated bounded key-failover
gateway; the same stage completed without starting a new campaign.
The **first** timed TTS planning attempt then failed with a non-retryable
`SemanticMappingError: Semantic proposal must cover all unresolved cues`
on slide 13. The semantic model returned no valid mapping. That slide's
spoken computed velocity **20** was not present as an extractable literal
on any current-slide PDF text region; another slide likewise contains
derived numbers with no extractable PDF text anchors. Correctness of
the arithmetic was **not disproved**; visual equation/image proof was
**not independently attested by the text-only cue planner**. No cue plan,
new WAV, acoustic acceptance, video, or final G2 acceptance receipt exists.
The runner preserved its exact source/code-bound terminal TTS marker.
Do **not** restart that paid campaign or treat an empty model answer as
proof that its underlying mathematics is wrong.

**Cross-workflow prevention baked into normal code:** The private
`preflight_private_timed_acceptance` and direct
`microgen_timed_cue_planner.propose_plan` now share a no-provider,
full-deck check that rejects spoken numeric values not attested by
extractable PDF text *before* any semantic proposal request. The shared
`microgen_cue_semantic_mapping.numbers` now correctly recognizes
mathematical coefficients in compact extracted formulas such as `5t2`,
and canonicalizes equal decimal notation (2 and 2.0). It does NOT
evaluate formulas, accept unproved derived numbers, or weaken PDF/voice
acceptance. The active `gen_script_v13._compose_prompt` instructs
future source-grounded narration not to speak calculated values missing
from fixed slide text or verified source elements. Source-free regression
tests exercise the normal G2 batch preflight, direct planner, correct
visible-value acceptance, semantic provider non-invocation, and
mathematical-token extraction. A read-only replay on the preserved
**fresh real-source** deck now emits `UNATTESTED_VISIBLE_NUMERIC_CUE`
at slide 13 cue 2 with **zero new semantic requests**.

**Honest recurrence status:** Automatic failure signature classification
and **SAFE_STOP_VERIFIED**. This eliminates recurring *wasted* provider
requests for this literal-numeric evidence gap, but it is NOT proof of
automatic revision, domain proof for mathematically derived values, or
a successful G2 lecture. Reopening a new paid campaign requires a
materially revised source-grounded lecture candidate or a separately
verified source-PDF mathematical/visual cue mapping, within a fresh
independently authorized finite scope. No acoustic or timed video pass
is inferred from scientific QA alone. Keep G1 partially integrated,
G2 blocked, G3 unverified, and G4 not ready.


### 11 November 2026 — source-visible mathematics and exact cue auto-recovery

**Real causal root, not generic model instability:** On the November 11
Serway 2.5 17-slide G2 candidate, the production text cue planner used
`_pdf_text_blocks` with the condition `salient(label)`. This silently
excluded equation-only PDF vector text containing the computed result
and intermediate expressions. The previous printed-value detector was
therefore correct about *filtered blocks* but not about the actual source
slide. Independent PDF inspection found those values and source bboxes
already present on slides 13 and 14; the first failed semantic request
was asked to map a formula it could not see.

**Integrated reusable recovery in normal production paths:**
1. `microgen_timed_cue_planner._pdf_text_blocks` retains extractable PDF
   mathematical expressions with real bounded source coordinates, while
   rejecting image-only, page-number and insignificant spans. This fixes
   source-evidence omission in the shared lexical/private preflight planner.
2. `microgen_cue_semantic_mapping.exact_math_source_block` and the ordinary
   `_lexical_match` automatically ground a **unique**, source-visible
   initial/final numerical-velocity expression (full numbers, source state
   labels and units), or an exact dual symbolic identity such as a signed
   algebraic result and time-step limit. Wrong signs, variables, units,
   missing computed literals and duplicate candidate regions are rejected.
   These are source-text references, not new algebraic inferences.
3. All single-block lexical choices now require the *selected* original
   PDF block to contain the spoken numeric values; presence somewhere else
   on the slide cannot cover a contradictory selected block. Source-bearing
   multi-element semantic groups remain the bounded non-lexical fallback.
4. `source_grounded_speech_units` splits long spoken clauses at existing
   commas only when separate numerical claims are each actually printed
   in independent source blocks. It preserves all narration words and
   mathematical values, avoids giant merged highlights spanning distant
   title/formula positions, and uses the **same helper** for full-lecture
   preflight and actual cue-plan generation. No independent ASR, voice
   substitution, translation or mathematical invention is introduced.

**Evidence:** Read-only replay of the **previously failed exact 17-slide**
real PDF/narration showed equation math on slide 13 now contributes
**6** source text elements (rather than 2) and on slide 14 **8**
(rather than 2). The unique matched real numeric/math cues on slides
13 and 14 are now grounded *without* a Gemini mapping request.
The pure-source plan for this lecture has **70 speech cues** and requires
four semantically assisted slides `[11,13,14,15]`, which remains within
the unchanged maximum **4**. A source-quoted, model-free **offline
feasibility fixture** in a separate private shadow folder
`%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261111_HP_G2_MATH_GROUNDED_OFFLINE_SHADOW`
created a complete plan with original-SHA-bound PDF regions, and the
**actual `microgen_timed_cue_tts._verified_plan` accepted all 70 cue
regions**. This is **OFFLINE SOURCE-MAPPING FEASIBILITY**, not real Gemini
semantic screening, acoustic QA, generated voice, video, or G2 acceptance.
The terminal old campaign was not restarted or mutated.

**Regression evidence and release boundary:** Source-free tests cover
PDF formula-only block retention; no acceptance of page counters/images;
unique math/source unit anchoring; signed equation RHS rejection;
ambiguous duplicate-source rejection; numeric mismatch in a lexical
region; source-preserving comma cue splitting over distant bboxes;
full cue-plan generation and independent source-PDF verification; and
fail-closed behavior when no valid printed result exists. These
production-path fixes prevent this particular PDF-math omission on
future sources; they do NOT automatically approve model semantics for
remaining paraphrases, independent audio or final MP4s. No claim
of permanent G2 closure until a newly authorized source-bound campaign
produces real timed Flash-Lite WAVs, independent acoustic and decoded
visual receipts and a final private acceptance receipt.


### 11 November 2026 — automatic panoramic-figure LaTeX overfull-box recovery

**Latest real-source blocker:** The private, single-attempt HP Serway §2.5
G2 candidate on revision `5ed811e1e20e6506174395134588148a4c8ac396`
completed extraction, figure mapping and merge, then stopped in the
normal `slides` stage. The exact slide's `slides.log` reported
`Overfull \\hbox (21.916pt too wide) in paragraph at lines 93--93`.
The preceding `\\includegraphics[height=0.4\\textheight,keepaspectratio]`
for the panoramic original `Figure 2.7.png` produced a displayed
width around 364pt, exceeding the slide's line width. The existing
`microgen_slide_reflow.repair_layout` only split multiple
exampleblock/column environments; this frame had neither kind of
splittable structure, so it compiled but failed quality twice on
identical TeX and correctly activated the anti-repeat guard.
Gemini 504 messages also occurred, but **the terminal failure was the
deterministic image geometry, not an equation or scientific QA result**.

**Reusable normal-path solution:** The existing shared
`microgen_slide_reflow.reflow_document(mode="graphics")` now proposes
exactly one minimally changed height-only image per candidate, adding
`width=\\linewidth` and preserving the original height ceiling and
`keepaspectratio` setting, original figure path and bytes, mathematical
expressions, frame order and slide count. Unknown graphics options,
already width-bounded graphics and custom geometric transforms are not
rewritten; all candidates still compile twice and must pass
`check_graphics`, `check_slide_pdf(require_footer=True)`,
`check_latex_overflow` and source math evidence checks **before**
transactional promotion of both .tex and .pdf with receipt and
source-hash-bound backup. The normal production
`gen_slides_v20.py` already invokes `repair_layout` on this precise
failure; no competing repair stage or per-PDF special case has been
introduced. Image fit candidates are prioritized ahead of destructive
slide-count splits. `microgen_quality.dependency_fingerprint("slides")`
now includes the shared reflow implementation and layout anti-repeat
guard so normal checkpoint reuse notices actual remedy code changes.

**Actual private failure replay with no Gemini:** A separate private HP
shadow copied the untouched failed `slides.tex` and original figure
assets, then ran `repair_layout` through genuine two-pass pdflatex.
Three bounded candidates were examined: unmodified normalized deck and
the wrong first panoramic figure retained the **21.916pt** overflow;
the third candidate constrained the correct Figure 2.7 and **passed**.
Result **18 PDF pages, zero severe overfull boxes, no math deletion**,
with source-verified backup and reflow receipt. The original terminal
paid stage and its source remained frozen. This is **REAL_SOURCE
DETERMINISTIC LAYOUT AUTO_RECOVERY_VERIFIED** in the actual production
reflow routine, but not yet full G2 audio/video acceptance.

**General regression proof:** New source-free fixture tests width-only
bounding, preservation of source figures and math, refusal of already
bounded or unrecognized graphics options, lack of frame corruption, and
invalidation of the slide stage when the reflow or guard implementation
changes. The live synthetic panorama also compiles through the same
reflow and quality gates on a TeX-enabled Windows machine. Existing
reflow/quality tests remain part of the full repository suite.
No model, TTS, acoustic or media receipt can be inferred from these
layout-only proofs; G2 remains blocked until a new, source-pinned
authorized campaign produces and independently validates them.


### 11 November 2026 — source-caption vector figure omission: autonomous normal-path remedy

**G2 root cause:** Private Serway section 2.5, commit 1de9b3715a33b4b1ecddadd439a94d8e098aea42, passed real figure extraction/mapping/merge but terminally failed the slides stage because source-grounded slides.tex referenced Figure 2.7.png and the original mapping produced only Figure 2.6.png, Figure 2.8.png and Figure 2.9.png. A previous diagnostic correctly produced three UNVERIFIED candidate regions, two partial graphs and unrelated textbook text; guessing one was prohibited. Intermittent Gemini 503/504 errors did not cause the terminal slide failure.

**Independent source facts:** The original immutable source PDF SHA-256 923c1768656433f29ba3a2ba413ea81eb5db9383f81d25873358b58709ae14aa includes a unique blue/bold Figure 2.7 caption on page 2 in a narrow right-hand column, directly below a multi-path vector graph with a/b panels, graph axes, labels, and mathematical annotations. A direct source-PDF render confirms the complete original figure.

**Integrated generalizable repair:** New microgen_source_caption_vector_recovery.py is invoked by the EXISTING normal graphics gate microgen_missing_source_figure_candidates.check_graphics_with_source_candidates. When one to three generated Figure X.Y.png references are missing, it searches the immutable source PDF for a uniquely styled numbered caption, requires narrow isolated source column geometry with multiple significant vector path components and independently extractable adjacent labels, extracts an exact PyMuPDF render of the entire justified region, and writes only previously missing figure assets using exclusive creation. It refuses ambiguous captions, unsupported/raster-only source diagrams, unknown graphic names, existing image overrides and invalid geometry; the previous UNVERIFIED candidate diagnostic remains the safe fallback. No OCR, Gemini, fabricated image or automatic human academic approval is involved.

**Provenance and recurrence:** Receipt .microgen_source_caption_vector_recovery.json binds the original PDF SHA, stable REFERENCED FIGURE IDENTITY digest, exact source page/bbox, output PNG SHA/pixel geometry and explicit science_qa_required True / publication_allowed False. Each later normal graphics check reopens and verifies that receipt, regenerates the PNG from original source coordinates to prove exact bytes, and rejects tampering or changed names. One new integration defect was independently reproduced: strict binding to the entire slides.tex bytes made a good recovered figure fail after legitimate two-pass normalizing reflow. This was corrected to bind source PDF and referenced figure identities, not unrelated LaTeX formatting. Slide/science/acceptance/published fingerprints and private completion manifest include the new source-caption receipt, and copying it during private publication is mandatory.

**Real G2 failure replay:** On a source-bound private HP shadow with original failed source.pdf, slides.tex and mapped figures, the normal graphics entrypoint autonomously recovered the complete Figure 2.7 and validated all FOUR images. Its regular repair_layout then compiled the actual failed presentation in ONE two-pass local candidate: 19-page PDF, zero severe overfull warnings, no math deletion. After reflow, the source-caption receipt remained independently valid with identical SHA. The original failed paid provider stage, source PDF and checkpoint were not altered and no new Gemini calls were made.

**Verification and limits:** Source-free tests include unique/duplicated captions, unsupported styles, insufficient graphic paths, unsafe names, image/receipt/source/crop geometry tampering, no overwrite of existing figure, harmless TeX reflow, changed figure identity, normal graphics re-entry, stage dependency fingerprints and release manifest provenance. Final designation can be CODE_INTEGRATED and REAL_SOURCE_NORMAL_PATH_AUTO_RECOVERY_VERIFIED after full exact-head regression/Windows CI; NOT G2_COMPLETE. The recovered vector figure is source-identical but still requires independently accepted academic/figure, narration, measured cue TTS, acoustic and decoded visual/video QA. Unmapped partial crops from figure extraction must not be declared independently covered unless proved; later release may be blocked by that separate coverage audit. Any new paid campaign requires a new fixed source/code-bound finite scope, never a replay of the terminal spent attempt.


### 12 November 2026 — G2 Gemini semantic JSON schema drift: fail-safe normalization

**Exact failed real-source stage:** HP Windows, original Gemini API-based
MicroGen_AI, Serway §2.5 source SHA256
`923c1768656433f29ba3a2ba413ea81eb5db9383f81d25873358b58709ae14aa`,
code SHA `4f1297ee047b2f2b93f8fd8d2700dc278251f50b`,
private campaign `20261111_HP_G2_CAPTION_VECTOR_RECOVERY_PRIVATE`.
Source figures, figure merge, slides, fresh 17-slide narration, independent
scientific QA and four-slide-budget preflight all PASSED. During first
timed TTS cue-plan proposal, slide 7 semantic model returned parseable JSON
that was not *exactly* a one-property dict `{"matches":[...]}`.
The normal `propose_with_gemini` raised `Unexpected model proposal schema`,
and the finite campaign terminally stopped before a verified cue plan, new
WAVs, independent audio QA, highlight video or G2 acceptance.
**The actual Gemini response JSON body was not preserved.** Do not assert
that a particular response variant was the historical one; that is
unknown. Existing stage receipt remains terminal; no provider replay.

**Reusable normal-path recovery:** The same production
`microgen_cue_semantic_mapping.propose_with_gemini` now invokes
`_parse_semantic_model_response` and `normalize_model_proposal`.
Within one existing budgeted model reply, without any retry or new key,
this accepts strictly equivalent JSON arrays, nested `matches` wrappers,
`result/data/output` wrappers, indexed cue mappings, bounded benign status
metadata, full JSON code fences, a JSON-encoded JSON body, parsed SDK
dict/list, explicit alternate `cue_id/cue_number`,
`block_id/block_index/source_quote`, grouped block IDs and quotes,
and integer indices written as decimal strings. The prompt states the exact
required JSON shape. A safe schema-shape diagnostic logs only top-level
field names/types and never raw textbook narration/model content.

**Mandatory invariants:** The adapter does NOT change narration, source
PDF, source figures, semantic slide budget or original voice. It
does NOT synthesize quotes, fill omitted cues, substitute unrelated source
blocks, rearrange group order or treat empty/error/rejected replies as
success. The unchanged `validate_matches` independently checks exact
verbatim PDF quotes, cue coverage, ordered/consecutive groups, visible
numbers and bounded source regions. The separate independent science,
acoustic, decoded visual and final acceptance gates remain required.

**Evidence:** Source-free tests exercise the real
`gen_script`-independent timed-planner entrypoint with injected
Gemini-equivalent variations, plus negative malformed/error/duplicate,
fabricated quote and numeral tests. The actual private 17-slide lecture's
slide 7 has 3 speech cues, one unresolved clause and 5 original PDF blocks.
A *synthetic alternative-format* proposal using four authentic adjacent
source blocks passed the normalizer and strict quote verifier **offline**,
with zero model calls. It is a feasibility example, NOT evidence of what
Gemini actually returned, independent academic semantic approval, an audio
pass or a completed video. Previous G2 provider budget is NOT reset.
G2 stays BLOCKED pending new independently scoped live source/TTS/audio/
video acceptance; PR remains draft/unmerged.


### 12 November 2026 — prevent Gemini cue-response format drift at generation time

**Upstream terminal context unchanged:** The sole previously authorized
private Serway §2.5 HP attempt (source SHA
`923c1768656433f29ba3a2ba413ea81eb5db9383f81d25873358b58709ae14aa`)
completed source/figures/slides/narration/science QA and failed during
the first timed-cue semantic request on slide 7, with
`Unexpected model proposal schema`. The raw response shape was not
retained, so neither its exact representation nor scientific adequacy
is established. No new provider authorization has been issued; never
restart the exhausted stage on a generic `Proceed` instruction.

**Generalized two-layer repair in normal Gemini request path:**
`microgen_cue_semantic_mapping.propose_with_gemini` already has a
strict deterministic adapter for harmless response wrapper/index
variations, with original-PDF `validate_matches` unchanged.
To prevent recurrence *before response parsing*, the existing one-call
`client.models.generate_content` now sends the provider-native
`response_json_schema`, alongside `application/json`, containing
a root object with a mandatory `matches` list. Each item is
one of two strictly typed/required source-evidence forms: a single
cue/block/verbatim quote, or a cue plus two-to-five ordered source
blocks and corresponding verbatim quotes. `additionalProperties=False`
rules out unsupported row/root fields. Crucially `matches: []`
remains representable for an abstention: failure must not force the
model to invent a quote. The old duplicate `output_contract` examples
were removed from the prompt; content instructions still stress full
coverage and printed-PDF evidence.

**Layered verification remains essential:** The schema constrains JSON
syntax/structure only. The existing adapter checks completeness,
and `validate_matches` checks exactly the original page's block
indices/order, verbatim source text and visible numbers; downstream
quality checks independently verify math, timing, audio, active-element
video and source hashes. A schema-valid `matches: []` on an unresolved
cue remains a **non-retryable failure**, not a science pass.
No provider/key/retry/voice/budget/rights controls changed.

**Non-billable evidence:** The installed HP Google GenAI SDK
v2.28.0 accepts the exact `GenerateContentConfig` JSON schema with a
two-form `anyOf` union. The production `propose_with_gemini`
request is tested with an injected one-send Gemini client, asserting
the literal schema in its model config and normal original-PDF quote
postcondition. Negative tests verify empty-array abstention stops
without a second send, unsupported response shape fails, and the prior
schema normalization path remains intact. These are offline proofs of
source/checkpoint-conserving code integration, **not** a successful
live Gemini structured-output call or G2 media acceptance.

**Release status:** G1 PARTIAL (the updated code remains within open
draft PR #291, not merged main), G2 BLOCKED pending a newly and
explicitly bounded real-provider campaign with independent acoustic
and decoded video acceptance, G3 NOT VERIFIED, G4 NOT READY. Do not
reclassify CI or local simulation success as a live G2 pass.


## Owner Amendment v1.1 — 12 November 2026: autonomous private development and TTS

**This supersedes contrary historical approvals clauses**, including the
earlier wording that required a new manual `--authorize-provider-usage`
for every new bounded HP G2 campaign. The owner explicitly authorizes
autonomous ordinary development and required private lecture TTS. The
implementation and source of truth are
`microgen_private_dev_policy.py`,
`microgen_campaign_authorization.py`,
`microgen_batch.py`,
`microgen_flash_tts.py` and `microgen_timed_cue_tts.py`,
with production-path regression tests. Text alone is not an implementation.

### A. No manual intervention for authorized development

No approval or human review shall be requested at individual figure, slides,
script, cue-mapping, science QA, TTS, acoustic QA or video stages. The owner
standing grant allows the **normal** HP `microgen_batch.py` invocation to
freeze a new private G2 or bounded TTS campaign without supplying
`--authorize-provider-usage`, provided ALL the conditions hold:

- The authorized host is HP and the repository is the original
  `MicroGen_AI` checkout, not `MicroGen_AI_Web`.
- Exactly one source subsection per new work root, stage endpoint
  `tts` or `acceptance`, private under the local MicroGen checkpoint root;
  no multipart expansion, public upload, source overwrite, or distribution.
- One first-use standing campaign **per original-source SHA256 plus exact
  Git commit**, across work-root renames or ChatGPT session changes, guarded
  by an **exclusive, durable local ledger**. The source, commit, voice,
  provider choices, Cloud ceiling and retry limits are frozen in the usual
  authorization receipt. A terminal failed stage is never silently replayed.
- Stage retry budget **0** for standing mode; existing finite per-model
  fallback/queue attempts and Gemini API-key failover remain bounded. A
  changed source, host, code, model, provider, text or voice invalidates
  earlier acceptance. No fresh provider retry is inferred from a new chat.
- Unknown host, arbitrary account/provider, unbounded job, non-G2 endpoint,
  already-spent source/commit pair, ambiguous potentially billed operation,
  unsafe file, and external publication remain fail-closed; they do not
  trigger a manual approval loop inside the authorized development pipeline.
  They do not count as successful lecture completion.

Previously authorized exact-scope resumes are automatic. This amendment is
the owner's standing authorization **within these finite limits**, not a
permission for unlimited paid API requests or an override of provider
service/usage policies.

### B. Formal TTS, model order and permitted fallback

When real lecture content requires speech, the private G2 pipeline **must
attempt authorized TTS autonomously**, subject to the verified cue plan and
existing source/voice/acoustic/visual QA. The authoritative default order is:

1. **Primary: Gemini 3.8 Flash-Lite TTS**, ID
   `gemini-3.8-flash-lite-tts`, voice `Kore`.
2. **First fallback: Gemini 3.8 Flash TTS**, ID
   `gemini-3.8-flash-tts`, same voice `Kore`, only if the first fails.
3. **Last-resort fallback only: Google Cloud Chirp 3 HD**,
   voice name `en-US-Chirp3-HD-Kore`, only after both Gemini choices fail,
   with valid existing Cloud credentials and a source-bound maximum of
   **40,000 attempted input characters per private campaign**.
   The Cloud fallback is now covered by this standing owner grant; no
   repeated manual confirmation is required. If the source text exceeds
   its Cloud budget, Gemini synthesis remains allowed while Cloud is
   disabled for that batch.

No Cloud TTS as a primary default. No mixing Gemini and Google Cloud
speech **inside one accepted lecture**. On provider failure, start a
**whole-lecture single-provider candidate**, preserving unmodified old
source and outputs until all PCM, source/WAV, voice and timing checks pass.
Cloud narration is not claimed acoustically identical to Gemini simply
because the speaker names correspond; independent acoustic QA is mandatory.
The TTS queue has **two finite attempts per cue/provider** in standing mode.
A fallback is not a way to hide non-speech, source drift, scientific
inconsistency, mixed voice or unknown model access.

### C. Verification and gate disposition

Proof of implementation requires a source-free production-entrypoint test
with **no approval flag** and exact provider-scope receipt/ledger, a
same-source/commit duplicate refusal, terminal replay refusal, host/retry
scope rejection, the correct 3.8 model and voice order, complete
Gemini-to-Cloud failover, no mixed-provider WAVs, bounded Cloud attempts,
and source/voice provenance checks. Also require the full HP Windows
pytest suite and Windows-only GitHub Python 3.11/3.12 CI for the exact
pushed SHA.

This amendment removes **repeated approval as a development blocker**.
It does NOT transform previously failed G2 media into a pass. G1 needs
code integration; G2 still needs newly generated real-source private
timed audio, independent acoustic QA and synchronized video receipts;
G3/G4 remain separate release gates.


**Security binding for standing consent (owner record, installed on HP):**
The no-manual-development grant is usable only when the private, non-Git
`%LOCALAPPDATA%\\MicroGen_AI_Checkpoints\\.microgen_owner_private_development_consent.json`
matches `microgen_private_dev_policy.OWNER_CONSENT_RECORD` exactly.
The owner authorized its creation in this session. The record has no
credentials, source text, API tokens or personal account identifiers.
A Git clone, missing/tampered private record or other PC must fail before
billed requests. Resume of an exact granted campaign works without repeating
this installation, but a prior terminal paid failure still cannot replay.


## 12 November 2026 — Standing source-quote evidence recovery (reused historical fixes)

The G2 Serway §2.5 slide-11 terminal semantic error `Quoted evidence not
present in rendered PDF text` is **not** a Gemini outage, a formatting-only
success, or permission to waive source evidence. The actual earlier model
reply was not preserved, so its cause cannot be guessed retrospectively.
The previous authorization is consumed.

Reusable historical principles:
- PR #258 / commit `562d47a` recovered a PDF superscript-reflow citation
  using only unambiguous ORIGINAL-source text, never invented text.
- PR #291 commits `79b932b` and `141c013` normalized harmless Gemini
  JSON shapes and constrained the response schema, without changing the
  independent source-quote verifier.
- PR #291 commit `cf1b71e` safely matched adjacent numbered question/answer
  PDF blocks with numerical and lexical source checks.

**Binding normal-path rule:** `microgen_cue_semantic_mapping` now supplies
a bounded provider-native list of *exact source-PDF quote excerpts* when
feasible, and the existing `microgen_timed_cue_planner` can relocate a
model's genuine quote only if it occurs in exactly one real visible source
block, the recovered blocks remain contiguous and ordered, the spoken
numbers exist there, and at least two lexically corroborating terms match.
It must never invent a quote, replace an unsupported number, infer academic
truth, move a duplicated quote, waive an unrelated quote, or turn a failure
into acceptance. Existing independent PDF, narration, TTS, PCM, acoustic and
decoded-video checks remain mandatory; semantic_mapping_certified stays
false.

**Recurrence evidence:** On a failed original-source semantic validation,
the regular HP private G2 path preserves a bounded single-slide model
proposal in a local SHA-bound private evidence file only under the
authorized isolated workroot. No source text or failed proposal enters
stdout, Git, published artifacts, or the source tree. If preservation
cannot be secured, fail closed; no repeated paid attempt is inferred.
Original unchanged failed campaigns remain terminal. New source/code
campaigns remain finite and ledger-guarded under owner contract v1.1.
Regression must include a real generated PDF page, misindexed genuine
quotes, grouped evidence, false/duplicate/unordered/unsupported claims,
SDK schema serialization, local-only failure evidence, full Windows
tests and exact-head CI. No Ubuntu, local model or repeated per-PDF fixes.


## 12 November 2026 — G2 acoustic risk prepayment prevention and private reviewer evidence

The real 17-slide Serway §2.5 G2 attempt generated **60 verified PCM cues** in the
unchanged Gemini voice, but the two-model independent acoustic gate rightly
stopped at `SOURCE_PRONUNCIATION_RISK_HOLD`. Seven slide-level holds arose from
source notation, alongside three disputed ASR slides and a separate targeted
audio-repair candidate. Keep this terminal run immutable: the WAVs and one-use
paid authorization are not a license for an unchanged replay.

**Recycled code remedies:** Previous `text_to_speech_v25.normalize_scientific_speech`
already handled `x of t` as `ex of tee` and mathematical letter compounds;
`microgen_pronunciation_closed_loop` contained conservative text-expansion
rules. `microgen_reviewed_math_voice.reviewed_math_voice` extends only
unambiguous mathematical-component forms (e.g. `a x`, `v sub x`,
`d squared x`, explicit `time t C`). It NEVER changes original textbook
`source.pdf`, rendered slides, or the visible `script.txt` narration.
The generated `script_tts.json` now stores only the explicitly spelled
voice input together with SHA-bound hash-only preflight evidence,
`phoneme_certified=false`, and `publication_allowed=false`.

**Normal-path fail-fast:** New private G2 calls `preflight_voice_sidecar` at
its existing TTS stage before the first external paid send. An imported
historical script with remaining unreviewed mathematical letters is rejected
with `PREDICTABLE_MATH_VOICE_RISK_PREPAY_HOLD` rather than billed for a known
source-risk acoustic failure. The new narrator only emits a voice-ready
sidecar if these deterministic source risks have been resolved; separate
two-model actual-WAV acoustic QA is ALWAYS required. Source risk reduction
is NOT pronunciation certification.

**Replay evidence:** A failed two-model acoustic review now keeps a bounded
SHA-bound private record of both ORIGINAL blind ASR transcripts under the
owner's local authorized HP campaign. No transcript, model output, credential,
or copyrighted source text is logged to stdout, committed to Git, or included
in a publication bundle. Previously saved blocked counts are not silently
converted to transcripts. The original gate remains fail-closed on
unavailable or conflicting recognition and limits same-voice audio repairs
to the existing two-slide ceiling.

G2 remains **blocked** until actual corrected-source voice audio, independent
acoustic QA, synchronized video and final acceptance pass. No extension of
owner authorization, automatic release, Ubuntu CI or local model is implied.


**Four-stage selective upstream reuse:** The previous generic reuse contract
could import all six accepted upstream stages, including old narration with
predictable ambiguous source math. This would cause a new pre-TTS hold before
the revised narrator could operate. The standard
`microgen_verified_upstream_reuse.maybe_import_verified_upstream` now
**reverifies the earlier complete six-stage source**, but when the earlier
voice-sidecar has an independently detectable math risk, imports **only**
figure extraction, figure mapping, figure merge, and slides. It imports
neither old narration/science receipts, narration caches, WAVs nor failed
provider attempts; current normal processing then regenerates and re-verifies
narration and scientific QA, followed by new finite TTS and acoustic QA.
A genuinely safe prior voice sidecar still permits all six stages to be
reused. Malformed historical evidence is refused rather than silently
promoted. Both four- and six-stage receipts are hash-bound, source-bound,
code-revision-bound and independently validated before downstream release.


## 12 November 2026 — Reusable science/acoustic closure improvements

The historical scientific QA and acoustic QA modules already enforce strict
source quoting, independent re-review, model-key failover, model disagreement
classification, bounded same-voice repairs and fail-closed provider budgets.
These safeguards remain authoritative. Green offline tests do not establish
real G2 independent QA acceptance.

**New source-bound narration recovery:** A terminal narration campaign may
preserve complete returned Gemini response batches even though its narrated
voice-preflight failed. The regular private G2 importer may copy these
records ONLY when the original PDF, slides, narration generator code and
original prompt-template hashes match. It carries NO completed narration,
science QA, TTS/acoustic receipt or authorization. Each original batch is
then independently verified against the full current source+model+prompt
request key inside the established generate_batched normal path. A drift
or unrecognized request requires normal finite failure handling, never
silent promotion. The 17-slide Serway 2.5 source shadow verified three
batches reused and zero extra model calls. Raw cached model replies stay
PRIVATE; published-manifest validation can verify their SHA manifest without
exporting the raw cached responses.

**Scientific reviewer format and spoken variable corrections:** Reuse the
existing Gemini-native JSON schema method (141c013) to force structural
17-slide scientific-review responses, without presupposing a pass. The
original source-PDF, quote-containment, ordered review, strict issue schema
and second model re-review rules still apply. For source-verified plain
narration corrections, when the exact observed written quotation is absent
from voice text solely due to previously reviewed math-letter expansion,
the normal QA may locate the uniquely matching spoken equivalent only
under a SHA-valid voice preflight receipt; otherwise it must fail closed.
A correction updates visible narration, spoken TTS and its voice-input
fingerprint atomically, then requires a fresh independent source recheck.
Unsafe/fabricated numerical corrections, non-source citations, duplicate
matches and unbound spoken mappings remain prohibited.

**Acoustic stage unchanged in its academic gate:** The existing independent
two-model ASR assessment, bounded repair rules, source-risk safeguards and
no-replay authorizations remain mandatory; a pre-TTS reduction in predictable
letter-name risks is only a source-input screen, never acoustic certification.
Only real independent science, acoustic and decoded visual/video receipts
can close G2. Publish/merge remains separate from private acceptance.


### Dependency-aware source reuse after scientific-review code changes

A fresh HP private G2 acceptance attempt on the newer scientific QA
implementation exposed a recurring false all-or-nothing invalidation:
the old **six-stage** QA receipt no longer validates under the upgraded
reviewer's implementation hash, even though the original PDF, figures
and slides are unchanged. The runner correctly refuses stale scientific
approval, but MUST NOT use that rejection to force repeat source extraction,
figure-caption provider calls or slide generation.

The normal prior-campaign selector now independently rechecks each of
the FOUR reusable source/art stages against its existing SHA-bound
fingerprints and real output validators. A six-stage import is permitted
only when current-code validation of BOTH narration AND science QA
also passes and the voice sidecar passes preflight. Otherwise it imports
FOUR stages only, preserving the source/deck and omitting old narration,
science receipts, WAVs and provider approvals. Independently returned,
source-and-prompt-bound narration batches may be re-imported as untrusted
private caches; the current generator must independently recheck their
original keys, and all QA must run again. An old malformed voice sidecar
can no longer force expensive reprocessing of valid source/slide evidence.

Never backdate or fabricate the independent scientific QA receipt.
Tests must reproduce scientific implementation drift and source-hash
tampering; real-source read-only verification must prove four-stage
reuse without provider calls. Previously consumed figure-mapping/G2
campaigns remain terminal. Any new paid campaign needs a fresh, finite,
source-and-code-bound authorization scope, and no publication occurs
until actual acoustic and technical acceptance passes.


### Source-attested preceding numerical-context recovery

In the 17-slide Serway G2 campaign the independent scientific review
passed, but timed-cue semantic mapping stopped before audio on slide 11:
Gemini selected a short visible heading for a cue containing two explicit
time values; the exact values were printed in the immediately preceding
problem-statement block. Previous numbered Question/Answer and unique
verbatim quote repairs were too narrow for this unnumbered heading pattern.

The NORMAL `microgen_timed_cue_planner` now invokes
`repair_preceding_numeric_context_heading` before the existing
unchanged `validate_matches` gate. The repair may expand a single
short, uniquely rendered, source-quoted heading to a contiguous
predecessor+heading group ONLY if the spoken cue has at least TWO
exact variable/value pairs, both are present verbatim in the preceding
source-PDF block, the spoken cue lexically identifies the heading, and
all spoken numerical claims remain source-supported. It carries the
original source text as an exact additional quotation and must pass
the independent final numerical, geometry, ordering, and PDF textbox
verification. No invented quote, paraphrase, numeric approximation,
unrelated or non-adjacent block is allowed. Absence of exact proof
remains a terminal source-evidence hold; no unchanged paid retry.

A private read-only replay of the exact failed PDF validated all three
model-proposed numerical cues, including the recovered two-element
region at 16.7% of the PDF page (<40% limit), using zero provider calls.
Synthetic normal-planner and adversarial tests cover incorrect variables,
mismatched decimals, nonunique headings and forged quotations.
The prior one-use campaign remains terminal and its independent
scientific QA result is preserved; a separate finite campaign can
revalidate that SHA-bound QA receipt without repeating scientific
review if the underlying implementation and inputs are unchanged.


### 13 November 2026 — Independent acoustic reviewer formatting and transport recovery

The genuine Serway section 2.5 G2 candidate completed 17-slide source science
QA, 71 timed source-grounded PCM cues and 88 WAVs on HP; the independent
Gemini 3.5/3.8 audio screen then failed with a **five-slide disagreement
and five-slide mismatch** record. The code correctly left the campaign
terminal and preserved original model-blind transcripts, WAV and SHA input
snapshots privately. NO video or publication approval was issued.

Prior fixes `c3b7add`, `264cb19`, `ad4a818`, `c59c58d`
and `b850892` already provided finite ASR key-pool fallbacks,
transcript short-response recheck, two-model disagreement categories,
no-billing-unchanged-input safeguards, and immutable private failed-ASR
evidence. **Do not remove or weaken these.** The new robust remedy
extends these normal paths:

- Normalize expected-blind reviewer **orthography only** with
  `microgen_acoustic_math_transcript.py`: explicit spoken vs printed
  mathematical components (vee ex/v_x, ay ex/a sub x), selected equation
  operators, decimal points, actual SI units, and exact polynomial
  exponents. Preserve every sign, decimal digit, mathematical exponent,
  source letter identity, and negation. The existing conservative
  sensitive-token and 5% discrepancy gates still operate.
- Require **strict JSON transcript-only** responses from both independent
  Gemini audio models, using the same provider-native response schema
  established earlier for independent scientific review and semantic
  source-grounded mapping. No expected narration text is EVER sent to
  either recognizer.
- Detect a recognizer returning its own drafting/explanatory notes in
  place of audible lecture words; use the existing bounded **one
  independent recheck** per affected WAV/model, without modifying
  original audio or fabricating script-based text. Invalid repeat
  remains rejected. Key pool rotation and hard retry budgets are
  unchanged.
- Bind the new mathematical reviewer module to the normal
  `acoustic_qa` stage dependency fingerprint, but NOT the `tts`
  fingerprint. Future changes invalidate a prior acoustic approval,
  not previously source/provenance-verified audio.
- Preserve original model-blind evidence and a private SHAs-only issue
  summary. An offline replay of the existing genuine 17-slide dual-ASR
  evidence under the revised conservative mathematical comparator
  yields **16 clean slides** and only **slide 5** blocked by a clearly
  malformed/explanatory independent reviewer response. This is a
  diagnostic **without new model calls**, NOT an acoustic pass, and
  no old terminal G2 campaign may be replayed unchanged.

This is a reusable automated protocol, not a waiver of independent
phonetic checking. Mathematical mistakes, incomplete transcripts,
speaker slips and ambiguous source evidence remain blocked. New
provider calls require fresh finite, owner-authorized HP campaign
scope. G2 can close only on actual independent acoustic, visual
synchronization and complete accepted video evidence.


**Safety correction after the exact-head HP suite:** The historical
`test_genuine_sensitive_or_out_of_scope_differences_remain_visible`
revealed that normalizing every isolated "tee" to a letter `t` was
too broad. The rule is now restricted to explicitly identified
mathematical phrases (`time tee`, `versus tee`, `d tee`, or a
source-grounded signed coefficient such as `minus see tee`). Generic
`tee` vs `t` remains a visible mismatch. The complete original
17-slide private transcript replay still yields only **one
malformed reviewer response** (slide 5) requiring a genuine bounded
audio-model recheck. This diagnostic is not an acoustic pass.


### 13 November 2026 — Recycled source-grounded voice remediation from independent acoustic consensus

A fresh source-bound private Serway 2.5 candidate on commit
`6268b40` generated 71 grounded source cues / 88 WAV files, but **did
not pass** independent acoustic QA. The original private dual-review
evidence (never published) classified slide 5 as a recognizer
disagreement and slides 4 and 17 as source-math-word pronunciation
candidates. Both independent reviewers saw the slide-4 expression
as an **equality** rather than the intended component-plus-grammar
phrase; both also reported an unwanted **square exponent** on the
slide-17 cubic polynomial. These are not safe ASR formatting waivers.

The normal `microgen_reviewed_math_voice` source-only pre-TTS
adapter now expands precisely source-confirmed expressions into
fully spoken, semantically equivalent wording:
instantaneous x-direction acceleration before a limit; average
x-direction acceleration on a graph; and a polynomial with explicit
multiplication and preserved cubic exponent and minus sign.
The original `narration`, displayed PDF/equations and textbook
source are NEVER modified by this spoken-language adapter.

A private read-only replay across all 17 slide voices verified that
exactly **slides 4, 5 and 17** change; the remaining 14 are identical.
The transformation is idempotent, hash-bound by the already integrated
`tts_math_voice_preflight`, preserves mathematical values and has
zero unresolved predictable source pronunciation-risk flags.
Independent scientific review MUST recheck the changed TTS sidecar;
actual new TTS audio MUST pass both independent recognizers, the
sensitive mathematical mismatch checks, decoded visual synchronization,
strict per-video <600s packaging and final technical acceptance.
No earlier failed WAV, terminal paid attempt or ASR approval may be
promoted or replayed as a pass.

Future similar failures should be repaired through narrowly reviewed,
source-attested transformations at the narration-to-voice boundary
BEFORE generating audio, with counterexamples and whole-lecture
replay tests. Never replace a failed acoustic gate with acceptance
by guessing what the speaker meant.


**Fresh-source six-to-four invalidation after voice-policy upgrades.**
The private Serway shadow identified an integration defect after introducing
new voice wording: the old six-stage checkpoint was still considered valid
because the prior narration and science receipts matched their OLD input
hashes, even though the CURRENT reviewed voice adapter would transform the
saved TTS text. This would silently skip the very acoustic remedy being
introduced.

The normal, pre-provider `preflight_voice_sidecar` now requires a saved
voice sidecar to be fixed under the CURRENT reviewed voice adapter:
`normalize(reviewed_math_voice(tts_text)) == normalize(tts_text)`.
A drift raises `STALE_VOICE_ADAPTER_SOURCE_HOLD` rather than approving an old
voice input. The private upstream importer catches this specific old-voice
condition and imports only the FOUR independently validated source/figure/
slide stages, NOT stale narration, science, TTS or acoustic approval.
The source-bound, exact-request-key Gemini narration caches remain
available as UNTRUSTED batches; the current narrator must revalidate
every batch before rebuilding the voice text. A six-stage science-valid
receipt is only described as current-code-valid if its voice adapter also
passes. No replay of an old audio campaign, no fabricated science pass.

A real private source shadow verified exactly **3 voice-only slide edits**
(4, 5, 17), **14 unchanged slides**, all 3 exact Gemini narration batch
keys accepted, unchanged visible narration and source, zero residual
predictable pronunciation source risks, and **0 new model requests**.
The independent science reviewer, actual two-model acoustic WAV QA and
video/final release remain mandatory before G2 closure.


### 13 November 2026 — Reusable known-blocker recovery is a normal pipeline dependency

**Motivation:** Owner-required autonomous recovery is NOT satisfied by a
blocked stage leaving useful evidence for the next ChatGPT conversation.
A historical remedy must be executed by the ordinary G2 runner, with a
stable failure identity, finite actions, output SHA binding and regression
proof. New or contradictory evidence may not be silently considered a pass.

**Established normal-path remedies:** finite Gemini 503/504 key failover,
source-quote and numbered/adjacent PDF cue reconciliation with exact
mathematical values, deterministic reviewed mathematical TTS voice input,
source and narration checkpoint reuse, strict JSON-only independent
scientific/acoustic model responses, source-blind mathematical transcript
comparison, bounded rechecks of contaminated recognizer responses and
verified same-engine/voice candidate repair.

**Additional critical recovery (verified source-bound PCM reuse):** The
original private G2 runner previously discarded all earlier WAVs when
only independent acoustic QA implementation changed. It now calls
`microgen_verified_tts_reuse.maybe_reuse_verified_tts` at the **normal
TTS stage** in a NEW individually authorized HP private source/commit
scope, before another billable TTS request. It may copy existing original
PCM, per-cue chunks, timed-highlight and exact source cue provenance ONLY
when the source, slides, written/voice narration, 17 original per-slide
PDFs, prompt-bound cue plan, all producer code modules and provider/voice
configuration remain byte-identical. SHA and original audio manifest,
voice-preflight, source cue, audio metadata and measured PCM highlighting
are independently revalidated twice. A missing cue plan may be restored
only if it passes current source/PDF cue evidence verification.
Recovery is transactional, size- and file-inventory-bounded, and stores
an explicit SHA-bound receipt. It **does not** import the failed prior
acoustic review, ASR transcripts, paid provider authorization, video,
release authorization or publisher output. Both independent Gemini
recognizers MUST run afresh before advancing to video.

**Strict non-reuse cases:** A change to the source PDF, mathematical
narration, TTS voice policy, code affecting actual synthesis, cue ordering,
PCM WAVs or provider settings forces normal rerender/QA, never a false
acoustic pass. The real Serway G2 original PCM and all timed chunks were
independently validated in a read-only HP replay. The revised math-voice
policy is deliberately incompatible with its older WAVs; this is NOT an
acoustic-only change. Source-free regression fixtures prove same-source
PCM reuse, preservation of the unchanged SHA and denial on eleven
falsified code/source/voice/evidence cases. An additional real-source
isolated replay copied the 17 original PCM WAVs and exact chunk inventory
without any model request, while leaving old acoustic failures excluded.

**Unresolved limits:** Independent ASR can still be genuinely unavailable,
contradictory, or detect a real phonetic/math error. Finite provider and
same-voice repair budgets remain mandatory; unknown errors and
mathematically unsafe evidence fail closed with a typed terminal
diagnostic. In particular a changed slide WAV in **timed-cue** mode must
never be accepted without remeasuring corresponding individual cue PCM
segments and retesting synchronization. Do not claim G2 closed solely
because source stages, recovered audio or unit tests pass. Continue through
independent ASR, correctly synchronized <600-second MP4 parts and final
private acceptance only when each real check independently verifies.


### 13 November 2026 — Automatic second-model ASR recovery after verified key exhaustion

**Actual failure evidence:** The genuine new Serway §2.5 private G2 campaign
`20261113_HP_G2_AUTORECOVERY_064F_PRIVATE` independently source-reverified
its 17-slide scientific QA (zero unresolved issues), regenerated and verified
71 timed cue WAVs plus 17 slide WAVs under the revised math-voice policy,
and automatically advanced to acoustic QA. The Gemini 3.5 Flash audio
reviewer returned usable original-audio transcripts; **Gemini 3.8 Flash,
independent reviewer B, remained unavailable across the finite configured
API key pool**. The campaign correctly stopped
`Independent acoustic transcription unavailable for model pass(es) [1]`.
This is no evidence of erroneous phonemes. Old failed acoustic approvals
remain invalid, and NO video or publication was generated.

**Permanent normal-path remedy:** Under `microgen_autonomous_acoustic_gate`,
a completed original transcript screen now detects unavailable *model
passes*, separate from genuine review disagreement or source pronunciation
risks. It automatically attempts no more than TWO fixed, independently
audio-capable Gemini model alternatives (`gemini-2.5-flash`, then
`gemini-2.5-pro`) on the SAME unchanged WAV files, retaining the
hash-bound output of the working independent reviewer. A replaced reviewer
MUST independently transcribe all 17 WAVs; prior partial responses from
the unavailable model cannot be mixed with its replacement. The actual
distinct model identities, candidate attempts and finite status are
recorded in the private acoustic evidence and success/failure receipt.
The normal strict <5% transcript mismatch/sensitive-token/source-risk
screens, two-model requirement and correctable-audio repair rules remain
mandatory. A genuine disagreement or pronunciation discrepancy NEVER
triggers reviewer-model shopping merely to achieve agreement.
An alternate model that is unavailable to the user's API account or
does not support the exact JSON transcript endpoint is simply counted
as one of two finite unsuccessful candidates. No unbounded retries or
model/credential substitutions are allowed.

**Dependency-aware resumption:** This is a code change to acoustic
reviewer logic only. A new, separately authorized source- and code-pinned
private campaign MUST revalidate and reuse the original 17 slide PCM WAVs,
71 cue WAVs and source-bound timing/provenance under
`microgen_verified_tts_reuse`, without charging for a new TTS pass.
Both genuine independent reviewers still run under the new code before
video. A successful acoustic receipt automatically continues to
verified slide slicing, <600s multipart MP4 generation, decoded visual/
audio synchronization checks and private acceptance. An unavailable
alternative or genuine phoneme mismatch fails closed with its evidence.

**Development evidence:** Source-free and historical-provider fixture
tests simulate the original secondary-model key exhaustion, both bounded
candidate outcomes, reuse of all first-model responses, exact actual
reviewer identities, refusal to switch on genuine speech discrepancies,
and exhausted/forged-model failure. These tests do not, alone, establish
live independent audio approval. Actual new G2 model responses must be
obtained in the later finite campaign.


### 13 November 2026 — Source-protected minor acoustic differences and bounded independent adjudication

**Owner decision:** Do not block ordinary lecture generation on harmless
disagreements between Gemini acoustic reviewers. Still block obvious
pronunciation defects, incorrect or missing mathematics, numerical values,
signs, exponents, physical units, negations, major omissions, source-side
pronunciation risks, corrupt WAVs and unavailable independent evidence.
No local TTS/ASR model is a substitute for genuine Gemini reviewer evidence.

**Actual SHA-bound failure class:** Private Serway 2.5 G2 at
`20261113_HP_G2_ASR_FALLBACK_5D96_PRIVATE` generated and source-verified
17 original slide WAVs + 71 cue WAVs. Its production ASR fallback obtained
two distinct Gemini reviewer transcripts, but the previous one-size 5%
threshold blocked slides **6 and 11**. Original confidential reviewer
words were preserved in a private, hashed, unexported failure trace.
The original SHA-bound WAV, source TTS sidecar and original model identities
were verified before reading the trace.

**Implemented in the NORMAL `microgen_batch.py` acoustic production gate:**

1. The shared acoustic comparator and independent release-evidence validator
   both apply the SAME narrow minor-variation rule. For source narration of
   at least 30 words, each independent reviewer may have at most **9%**
   differences from the source, and the two may differ by at most **15%**.
   Every edit must be short (at most two tokens), with at most 5 edits and
   8 affected tokens per reviewer. Formula/letter aliases and standard
   units have explicit safe equivalences; unlisted mathematical changes,
   numeric/negation/unit changes, phonetic `circa/yay` flags, unintelligible
   speech and long missing material cannot use this pathway. The ordinary
   strict 5% rule remains for every genuine sensitive discrepancy.
2. Shared mathematical detection now catches **all digit-token differences**
   (not only numerals 0–10), numeric words above ten, and changed physical
   units. Approved symbol/abbreviation aliases such as `meters`/`m`
   are not misconstrued as changed units. These protections are enforced
   in the initial audio screen, candidate recheck and final independent
   receipt verification, not merely in a troubleshooting script.
3. After normal bounded dual-model retakes, exactly one additional
   **source-BLIND, independent Gemini reviewer** may be used on at most
   two mathematically ambiguous slides if (a) one original reviewer is
   already strongly source-aligned, (b) the other shows only the *specific*
   number/letter segmentation artifact `40` vs `4 t` (generalized to
   a tens digit such as `30`/`3 t`), (c) there are no other sensitive
   discrepancies or source pronunciation warnings, and (d) the third
   reviewer independently agrees with both the source and the already
   source-aligned original transcript under the strict 5% guard.
   The third model is selected from a fixed distinct-model priority list;
   it never sees the target script and no further models are shopped after
   an unfavorable third opinion. Missing evidence keeps the QA blocked.
4. The complete **original two transcripts remain preserved**, with a
   distinct SHA-bound third-model witness and its actual model identity,
   WAV and spoken-input hashes. Final validation recalculates every
   source/math mismatch and checks the claimed tiebreaker, rather than
   trusting a changed `assessment` string. A forged `PASS`, changed
   number, changed unit, missing voice/audio hash or model identity drift
   never yields acceptance.
5. After a genuine independent acoustic pass, the standing authorized
   private runner continues automatically to slide slicing, the correctly
   timed (<600-second-part) MP4s, decoded visual QA and final acceptance.
   Source/figure/science/TTS work and the 88 verified WAVs are never
   regenerated simply because reviewer scoring rules change. All
   provider calls retain the existing finite authorization and budgets.

**Verified offline historical replay:** With its authentic prior blind
Gemini transcripts, slide 6 now passes through minor transcript spelling
variations (`vee`/`v`, `tee`/`t`, `t a`/`ta`).
Slide 11 is deliberately still blocked by `40` vs `4 t`.
A **controlled, fabricated third-witness fixture** on the same genuine
SHA-bound inputs demonstrates the final verifier can accept correct 2/3
corroboration and reject tampered/source-inconsistent evidence; this is
TEST EVIDENCE ONLY, not actual third-reviewer approval. A later individually
authorized private G2 campaign must obtain real Gemini audio-review evidence
before claiming acoustic/video acceptance. Do not manually label slide 11
passed or publish old review failures.
