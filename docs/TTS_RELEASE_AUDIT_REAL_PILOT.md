# PR #32: End-to-end read-only TTS release audit and textbook pilot

**Superseded release-policy rule (2026-10-20):** The later autonomous QA
contract removes manual sign-offs as mandatory blockers by default. Historical
PR #32 descriptions below are retained for provenance, but active behavior is
specified by `AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md`. Technical
provenance, independent acoustic evidence, PCM and video checks still gate.


Run `python microgen_tts_release_audit.py PATH_TO_ISOLATED_LESSON_STAGE`. The release evidence matrix checks pronunciation preflight, reviewed lexicon, PR #24 pinned voice/WAV provenance, **independent acoustic** receipt, exact WAV hash-bound human listening for every slide, MP4 audio/video integrity and strict **less than 600 seconds**, plus separate video-hash-bound academic, figure and element-level highlighting approvals.

Any absent, stale or conflicting receipt is a named blocker. A complete check means **ready for a separately authorized promotion workflow**; this command can never publish. It does not synthesize or overwrite original audio. External review receipts must be authenticated/trusted by the publishing workflow rather than merely created by this CLI.

The Dell-115 read-only Thomas Calculus §2.5 pilot is expected to FAIL release readiness: this pre-PR24 review stage has a real verified MP4 and WAVs but lacks the new live pronunciation/voice receipts and the independent academic, element-highlight and complete listening approvals. The pilot may demonstrate the checker rejects a real incomplete historical video; it does not certify or automatically replace that video. Source, audio and historical production outputs remain untouched.
