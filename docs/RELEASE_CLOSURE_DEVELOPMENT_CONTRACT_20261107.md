# MicroGen_AI — Release Closure Development Contract

**Version:** 1.0 · **Effective:** 7 November 2026 (Asia/Kuala_Lumpur)
**Project:** original Gemini-API `tlyoon/MicroGen_AI`, not Selenium `MicroGen_AI_Web`.
**Mode:** RELEASE CLOSURE (default for all subsequent project-development invocations).

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
  separately authorized troubleshooting path or opt-in last-resort fallback,
  never the implicit formal default.
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
