# MicroGen_AI: Thomas Calculus 2026 reliability hardening

Repository: https://github.com/tlyoon/MicroGen_AI (not MicroGen_AI_Web).
The changes are software hardening only. Do not rerun production against the 66 completed Thomas folders merely to smoke-test a new branch.

## Lessons incorporated

- A nonempty PDF or MP4 is **not** a completed lecture. Strict validation now checks real PDF pages/counters, missing LaTeX figures, ordered sidecar narration, contiguous WAV files, MP4 audio/video streams and duration.
- Publication is built and checked locally first. A hash-bound `.microgen_verified_completion.json` is written last; previously published files receive protected backups, and publication attempts roll back on failure.
- The video engine retains hash-keyed per-slide MP4 segments and never deletes the old MP4 at the start of encoding. Plain static slides use 2 fps rather than 30 fps, reducing unnecessary frames.
- Gemini narration is partitioned into 8-slide batches (configurable 1–20) with validated, input-bound checkpoints. A large 54-slide request previously timed out with 504; batching recovered 8.5 successfully.
- TTS now verifies and caches each WAV, retains existing audio, and refuses mixed-provider voices. Windows SAPI fallback is opt-in; no silent switching.
- Beamer is compiled twice, with page counter and severe-overflow checks. Missing figures fail closed rather than silently disappearing. When a LaTeX compile fails, an isolated deterministic blank-paragraph repair is attempted and verified before asking Gemini to repair TeX. The original defective 8.5 pilot TeX passed this local method as a 10-page PDF without another API request.
- Temporary image/crop folders can be cleaned after verified publication, but WAVs and numbered slide PDFs remain available to resume and audit.
- `microgen_doctor.py` performs an offline, bounded source inventory and checks prerequisites without revealing credentials.
- Unit tests run on Python 3.11/3.12 across Windows/Linux; tests do not call paid APIs.

## Other users: setup

Clone `tlyoon/MicroGen_AI` to a local code directory and install dependencies. Install Python 3.11+ (3.11 or 3.12 tested), MiKTeX/pdflatex, FFmpeg or imageio-ffmpeg. Provide keys privately in `%LOCALAPPDATA%\Microvid\.env` or `MICROVID_CONFIG_DIR` and service-account credentials in the documented default folder. Never put secrets in GitHub.

Specify an explicit, writable *source root* containing `<chapter>/<subchapter>/source.pdf` and a **separate local-disk work root** for heavy tasks.

Read-only preflight:

```powershell
python microgen_doctor.py --source-root "G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed" --audit
```

Example only, against an **isolated source-authorized test copy**, not the completed Thomas tree:

```powershell
$env:MICROGEN_LLM_MODEL = "gemini-3.8-flash"
$env:MICROGEN_NARRATION_BATCH_SIZE = "8"
$env:MICROGEN_STAGE_TIMEOUT_SECONDS = "7200"
python microgen_batch.py --source-root "D:\LectureSources" --work-root "D:\MicroGenWork" --targets "1.1"
```

For multiple PCs, distribute disjoint subchapter IDs, pin the same tested commit, and share a `MICROGEN_GEMINI_LANE_DIR`. The Gemini lane serializes API requests but does **not** by itself provide a strong source-publication lease. Cloud Drive folders must not serve as computational scratch space.

## Important limitations and next release gates

The implemented `microgen_lesson_plan.py` is an **offline planning foundation only**. It accepts source-grounded semantic scene inputs and plans coherent part boundaries; it is **not integrated yet** into the full slide/narration/MP4 production pipeline. It does not itself split the 30-minute 8.5 lecture into three or four coherent videos.

True word/phrase-synchronized highlighting, verified figure subpanel/caption provenance, full cross-PC job ownership, automatic repair of clipped but compilable Beamer slides, and end-to-end clean-install piloting **remain outstanding**. The 66 Thomas MP4s are not thereby scientifically certified.

Run locally before merge:

```powershell
python -m compileall -q microgen_quality.py microgen_batch.py microgen_narration_batch.py microgen_lesson_plan.py microgen_doctor.py gen_script_v13.py gen_slides_v20.py gen_video_v22.py text_to_speech_v25.py
python -m unittest discover -s tests -v
```

Release sequence: isolated unit tests -> independent Windows/Ubuntu CI -> fresh controlled test-copy generation -> inspection of actual PDF math/diagrams and audio -> only then merge/deploy to the three PCs at safe worker boundaries. Older output receipts are not silently promoted to new verified status.
