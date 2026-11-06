# Autonomous blocker recovery and release evidence (MicroGen_AI)

**Project scope:** the original **Gemini-API-based** `MicroGen_AI`. This
document does **not** apply to `MicroGen_AI_Web` (Selenium). Only Dell-115
is authorized for this release validation. No local language or speech model,
no Cloud TTS as the default, and no automatic external publication.

## Recovery mechanisms built into the package

| Prior recurring blocker | General code recovery | Guardrail |
| --- | --- | --- |
| Installed `google-genai` imported but lacked `HttpRetryOptions` | Both batch preflight and installation doctor now **exercise** the HTTP retry API before any paid generation. | Report which selected interpreter needs `google-genai>=2.33,<3`; never silently modify the global installation or rotate keys to treat an SDK defect as a capacity outage. |
| FFprobe absent or FFmpeg lacking H.264/libx264 | Batch preflight scans PATH, explicit configured executables, `%LOCALAPPDATA%\Microvid\media_tools\bin`, and bounded existing isolated release tool folders. It tests FFprobe and the H.264 encoder, setting `MICROVID_FFMPEG` and the **current process's** PATH when an installed pair works. | Offline discovery only, no package download, installation, system PATH change or untrusted executable fallback. Fail early with actionable guidance if no valid binaries exist. |
| Old queue ticket blocked the next Gemini call for about an hour after a process crashed | Lane cleanup identifies **same-host** tickets belonging to a verified dead Windows PID or one reused after ticket creation, and archives the ticket atomically. | Check PID creation time, ticket host/token/age, and heartbeat grace. Never terminate a process, inspect another PC's PID, or delete an unverified ticket. Other-host tickets retain existing stale lease rules. |
| Gemini 503/504, read timeout, key-specific failures | Existing `gemini_keys` pool rotates the configured keys with bounded retries and backoff. | Do not treat all 503 responses as proof of quota depletion. Never display the key contents or retry without bounds. |
| Misleading acoustic failures despite valid TTS | Separate unavailability from pronunciation risks; canonicalize demonstrably equivalent ASR spellings; allow one blind retake for truncated transcripts and at most two disputed clips with both independent models. | Protect negative signs, quantities, variables and named mispronunciations such as `c` / `circa` or `y` / `yay`; never supply the script to blind recognizers, issue a forged receipt or silently approve a real disagreement. |
| A previously blocked acoustic report obscured a newer attempt | Each failed run writes a new, timestamped, source-hash-bound, **status-only** diagnostic, including slide assessments and model discrepancy sizes. | No API credentials or full blind transcripts in the shared blocker record. |
| Repeated identical Beamer overflow or PDF page-boundary error after automatic structural reflow | `microgen_layout_retry_guard` detects an unchanged TeX digest plus identical layout error during the four local compile attempts. It saves a source/producer-hash-bound status-only diagnostic. Future runs reject the same unchanged failure **before** another paid slide-generation call. | Keep the original source, math and figures unchanged. Retry automatically only if the source, relevant source-backed TeX or general slide/reflow code has changed; do not loop to perfect one PDF. |
| Endless rework of individual source PDFs | Use stage fingerprints/checkpoints, bounded retries, fail-fast categorization and independent pilot source copies. | Resume only invalidated stages; no repeated PDF-specific perfection cycle. |

The preflight cannot manufacture missing binaries or resolve an actual Gemini
provider outage. Its role is to **recover installed local dependencies** where
safe and diagnose unresolvable external dependencies *before* wasting generation
work. A provider outage remains a bounded, logged dependency.

## Portable private media installation

Place a verified FFprobe and an FFmpeg with `libx264` in
`%LOCALAPPDATA%\Microvid\media_tools\bin` or use
`MICROGEN_MEDIA_BIN`. `MICROGEN_FFPROBE` and `MICROVID_FFMPEG`
may specify the two executable paths independently. The batch preflight
automatically detects these configurations without changing the system PATH.
If the installed FFmpeg lacks `libx264`, the preflight checks the already
installed `imageio_ffmpeg` binary before failing.

The main Python environment must use `google-genai>=2.33,<3`. A dedicated
virtual environment avoids changing a global Python or Docling setup.

## Verified private pilot and outstanding release dimensions

- **Serway 8.1**: 18-slide source-grounded slides, narration and Gemini
  Flash-Lite TTS completed. Independent two-model audio screen passed; zero
  audio repairs. Video parts were 289.68 s and 331.30 s. Technical receipt
  `PRIVATE_AUTONOMOUS_TECHNICAL_ACCEPTANCE_PASSED` and final merged-code
  checkpoint resume with exit 0. Full ~621 s MP4 was retained **privately as
  an archive**, not cleared for distribution. Publication is `false`.
- **Serway 8.2**: separate second-source private pilot; record its result in
  the release issue once the bounded run finishes.
- **Final release gate**: technical tests are distinct from copyright /
  distribution permission and from a proof of **element-level synchronized
  highlighting**. The private acceptance receipt does not certify either.
  Confirm each requirement independently before any external publication.
- **Cost / scope**: Dell-115 only; use Gemini or ChatGPT, not local models.
  Do not modify the original source PDFs or the original uncommitted
  Google Drive checkout during release tests.

See the durable GitHub release record at
`https://github.com/tlyoon/MicroGen_AI/issues/278` for run outcomes,
PR references and recorded remaining blockers.
