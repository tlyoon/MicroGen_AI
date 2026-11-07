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

## 2. Nonnegotiable operating constraints

- **Device isolation:** original MicroGen_AI development, real-media production,
  local QA and validation run on **HP only**. Dell-115 is for MicroGen_AI_Web;
  do not transfer these two repositories' runtime, contracts or machine rules.
  GitHub-hosted CI is allowed. Do not use Yoga6/Zenbook for this work.
  The older Dell-only statements in historical contracts/issues are obsolete.
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
| **G1 — Code integration** | Required modules and approved PRs (including pending semantic-cue work, if validated) are integrated into one coherent pinned main/release candidate. No duplicate implementations, uncommitted production changes or obsolete provider/device settings. | Exact Git SHA, main/PR comparison, focused and repository-wide regression results, hosted CI result or explicitly documented CI unavailability. |
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
