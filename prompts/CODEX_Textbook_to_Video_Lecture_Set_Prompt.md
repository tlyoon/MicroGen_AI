# Codex Prompt — Generic Textbook PDF to Slide Stack + Narrated Video Lecture Set

## Purpose

Use this prompt in **Codex running on a local computer** to generate a complete set of lecture slides and narrated MP4 videos from textbook/course subtopic folders containing `source.pdf` files.

The workflow uses the **MicroGen_AI** code package. For each selected subtopic it performs:

1. figure abstraction from `source.pdf`,
2. figure-to-caption mapping,
3. hybrid v6/v7 + pri slide generation,
4. hybrid narration generation,
5. Google Cloud TTS generation,
6. per-slide PDF/audio generation,
7. MP4 assembly,
8. integrity verification, and
9. storage cleanup after successful completion.

The final user-facing outputs remain inside the same subtopic directory as the corresponding `source.pdf`.

---

# USER-EDITABLE PLACEHOLDERS

Before running this prompt, define at least `SOURCE_ROOT_DIRECTORY`. All other placeholders have usable defaults.

```text
SOURCE_ROOT_DIRECTORY = "{{REQUIRED: absolute path to the textbook/project root directory}}"

CODE_PACKAGE_URL = "{{default: https://github.com/tlyoon/MicroGen_AI.git}}"
CODE_PACKAGE_REF = "{{default: main}}"

CODE_PACKAGE_FALLBACK_URL = "{{default: https://drive.google.com/open?id=1brjd9r0ttscg4MboQA63jbLempvvsBTM&usp=drive_fs}}"

LLM_MODEL = "{{default: V7_DEFAULT}}"

TARGET_SUBDIRECTORIES = "{{default: AUTO_FIRST_PARENT_ALL}}"

MICROVID_CONFIG_DIR = "{{default: AUTO}}"

GEMINI_LANE_DIRECTORY = "{{default: DISABLED; for multi-PC runs set the same synced directory on every worker}}"

WORK_ROOT_DIRECTORY = "{{default: AUTO}}"
```

## Meaning of the placeholders

### `SOURCE_ROOT_DIRECTORY` — required

Absolute local path to the root directory containing textbook/course folders and subtopic folders.

Example:

```text
D:\Teaching\Thomas_Calculus_13ed
```

A typical hierarchy is:

```text
SOURCE_ROOT_DIRECTORY/
├── 1/
│   ├── 1.1/
│   │   └── source.pdf
│   ├── 1.2/
│   │   └── source.pdf
│   ├── 1.3/
│   │   └── source.pdf
│   └── 1.6/
│       └── source.pdf
├── 2/
│   ├── 2.1/
│   │   └── source.pdf
│   └── 2.3/
│       └── source.pdf
└── ...
```

Only process valid subtopic directories that contain a readable `source.pdf`.

### `CODE_PACKAGE_URL`

Primary location of the MicroGen_AI package. The default is:

```text
https://github.com/tlyoon/MicroGen_AI.git
```

Use the `main` branch unless `CODE_PACKAGE_REF` is explicitly changed.

### `CODE_PACKAGE_FALLBACK_URL`

Legacy/fallback package location:

```text
https://drive.google.com/open?id=1brjd9r0ttscg4MboQA63jbLempvvsBTM&usp=drive_fs
```

The GitHub `main` branch is authoritative by default. Use the Drive location only when GitHub is unavailable or when the user explicitly selects the Drive package.

### `LLM_MODEL`

Default:

```text
V7_DEFAULT
```

`V7_DEFAULT` means: **do not override the model choices already defined by the current MicroGen_AI v7/hybrid package**.

At the time this prompt was written, the package defaults are approximately:

- figure mapping: `gemini-3.8-flash`,
- slide generation: `gemini-3.1-pro-preview`,
- narration generation: `gemini-3.1-pro-preview`.

Treat the code package itself as authoritative if those defaults later change.

If `LLM_MODEL` is changed to an explicit model name, for example:

```text
LLM_MODEL = "gemini-3.1-pro-preview"
```

apply it as the common runtime override by setting:

```text
MICROGEN_LLM_MODEL=<selected model>
```

Do not modify the repository permanently merely to change the model for one run.

### `TARGET_SUBDIRECTORIES`

Default:

```text
AUTO_FIRST_PARENT_ALL
```

This means:

1. Inspect the immediate child folders of `SOURCE_ROOT_DIRECTORY`.
2. Natural-sort them.
3. Select the **first parent folder encountered**.
4. Within that parent, natural-sort its immediate child folders.
5. Select every child folder containing `source.pdf`.

For example, if the source tree is:

```text
1/
├── 1.1/
├── 1.2/
├── 1.3/
├── 1.4/
├── 1.5/
└── 1.6/

2/
├── 2.1/
├── 2.2/
└── 2.3/
```

then the default target set is:

```text
1.1, 1.2, 1.3, 1.4, 1.5, 1.6
```

The user may instead provide an explicit selection, for example:

```text
TARGET_SUBDIRECTORIES = "1.3"
TARGET_SUBDIRECTORIES = "1.3,1.4,1.6"
TARGET_SUBDIRECTORIES = "1.3-1.6"
TARGET_SUBDIRECTORIES = "2/*"
```

Interpret explicit ranges naturally and only include directories that actually exist and contain `source.pdf`.

### `MICROVID_CONFIG_DIR`

Default:

```text
AUTO
```

On Windows, `AUTO` means use:

```text
%LOCALAPPDATA%\Microvid
```

and expect, as applicable:

```text
.env
Google Cloud service-account JSON credential file
```

The `.env` should contain the required API key, normally:

```text
GEMINI_API_KEY=...
```

The TTS stage expects a valid Google Cloud credential JSON file. Never copy credentials into the repository, source folders, generated outputs, logs, or chat messages.

On non-Windows systems, choose a secure per-user credential directory and export `MICROVID_CONFIG_DIR` to that directory.

### `GEMINI_LANE_DIRECTORY`

For a normal single-PC run leave this disabled. For coordinated multi-PC generation, set this to the **same shared/synced directory on every participating computer**, for example:

```text
G:\My Drive\MicroGen_AI\coordination\gemini_lane
```

Then export it as:

```text
MICROGEN_GEMINI_LANE_DIR=<shared path>
```

The package will serialize the Gemini-heavy stages across the participating PCs while non-Gemini work can still proceed independently. Do not launch multi-PC Gemini work unless every worker is using the same lane directory. The package also applies exponential backoff for transient Gemini `429`/`503`/capacity failures.

### `WORK_ROOT_DIRECTORY`

Default `AUTO` means create an isolated temporary/work directory outside the textbook source tree, for example:

```text
<user cache or temp>/MicroGen_AI_runs/
```

Do not use the source directory itself as the code repository. Keep source material, code, temporary files, and final outputs logically separated.

---

# EXECUTION CONTRACT FOR CODEX

You are the execution agent. Carry out the workflow to completion. Do not merely explain what commands the user could run.

## A. Safety and invariants

1. Never delete or overwrite any `source.pdf`.
2. Never expose, print, commit, upload, or echo API keys or credential-file contents.
3. Never alter unrelated files already present in a subtopic directory, including question banks, XML files, HTML files, notes, or other teaching materials.
4. Do not publish textbook PDFs or extracted textbook content to GitHub.
5. Perform destructive cleanup only **after** final outputs for that subtopic have passed integrity checks.
6. Use an isolated per-subtopic staging/work directory. Only publish verified outputs back into the corresponding source subtopic directory.
7. If one subtopic fails, record the failure and continue with other selected subtopics when it is safe to do so. Do not delete failed work needed for diagnosis.
8. Never report success for a subtopic until `slides.pdf`, `script.txt`, and `slides.mp4` have been validated.

---

# B. Acquire or update the MicroGen_AI package

1. Resolve `CODE_PACKAGE_URL` and `CODE_PACKAGE_REF`.
2. If the package is already cloned locally, verify its remote and update it safely to the requested ref.
3. Otherwise clone it into a dedicated local code directory.
4. For the default GitHub configuration, use the repository's `main` branch.
5. If GitHub cannot be reached, use `CODE_PACKAGE_FALLBACK_URL` only if it is locally/connector-accessible.
6. Do not make the source textbook hierarchy itself a Git repository unless the user explicitly asks.
7. Record the exact Git commit SHA used for the run in the final report.

---

# C. Automatically prepare the execution environment

The objective is zero manual package installation unless administrator approval or an unavailable credential makes automation impossible.

## C1. Python environment

1. Detect a supported Python installation. Prefer Python 3.11 unless the current repository documents a newer supported version.
2. Create a dedicated virtual environment for MicroGen_AI, preferably beside the local package cache, e.g. `.venv`.
3. Upgrade packaging tools:

```text
python -m pip install --upgrade pip setuptools wheel
```

4. Install the base requirements:

```text
python -m pip install -r requirements.txt
```

5. Install figure-extraction requirements:

```text
python -m pip install -r requirements-figures.txt
```

6. If an import required by the active pipeline is still missing, install the missing package and record it in the run report. Do not repeatedly reinstall packages that are already available.

## C2. Required external programs

Detect, and if absent automatically attempt to install, the external programs required by the active package, including as applicable:

- a LaTeX distribution providing `pdflatex` (MiKTeX on Windows or TeX Live elsewhere),
- FFmpeg,
- Poppler utilities required by `pdf2image`,
- Git.

Use the platform's available package manager when possible:

- Windows: `winget`, Chocolatey, or an already installed package manager,
- macOS: Homebrew when available,
- Linux: the distribution package manager.

Before installing by package ID, query/search the local package manager rather than assuming an ID that may have changed.

If installation requires elevation that Codex cannot obtain, report the exact missing dependency and command needed, then stop before generation rather than producing a partial or misleading result.

## C3. Credential validation

Without revealing secret values, verify that:

- the Gemini/API credential required by the selected LLM is available,
- Google Cloud TTS credentials are available,
- the credential files are readable by the current user.

Do not ask the user to paste secrets into chat. If credentials are missing, explain where the local credential files must be placed.

---

# D. Resolve the target subtopics

1. Validate `SOURCE_ROOT_DIRECTORY`.
2. Resolve `TARGET_SUBDIRECTORIES`.
3. When it is `AUTO_FIRST_PARENT_ALL`:
   - enumerate immediate child directories of the source root,
   - ignore hidden/system directories and obvious generated/cache directories,
   - natural-sort folder names (`1`, `2`, `10`, not lexicographic `1`, `10`, `2`),
   - choose the first valid parent folder,
   - natural-sort its child subdirectories,
   - retain only child directories containing `source.pdf`.
4. Print the resolved target list **before starting generation**.
5. If no valid `source.pdf` is found, stop with a clear diagnostic.

---

# E. Configure the selected LLM model

If `LLM_MODEL = V7_DEFAULT`:

- leave `MICROGEN_LLM_MODEL` unset,
- allow the current package to use its embedded stage-specific defaults.

If `LLM_MODEL` is an explicit model name:

- set `MICROGEN_LLM_MODEL` to that name for the run,
- preserve any explicitly user-specified stage override such as `MICROVID_SLIDE_MODEL`, `MICROVID_FIGURE_MODEL`, or `MICROVID_NARRATION_MODEL` if one was deliberately supplied.

Log the model configuration by **name only**; never log keys or credential values.

---

# F. Process each selected subtopic

For each selected subtopic directory, perform the following sequentially.

## F1. Create isolated staging workspace

1. Create a clean working directory unique to the subtopic.
2. Copy the current MicroGen_AI code snapshot into it, or otherwise make the package files available there without modifying the source repository.
3. Copy the subtopic's `source.pdf` into the staging workspace.
4. Do not copy unrelated source-directory files unless an active pipeline stage genuinely requires them.

## F2. Figure abstraction

Run the active/latest v7 figure-abstraction path. The package's version resolver should prefer the highest available versioned script.

Current expected logical stages are:

```text
crop_figs_v3.py
map_and_rename_v5.py
merge_lettered_figs_v2.py
```

Requirements:

- process the complete `source.pdf`,
- do not invent figure numbers,
- map extracted figures to actual source captions,
- use the code package's configured image-size threshold unless the user supplied a textbook-specific override,
- preserve mapped figure assets needed by the final slide deck.

If figure extraction produces no useful figures, do not fail the entire subtopic automatically; continue if slides can be generated correctly without figures.

## F3. Hybrid slide generation

Run the active/latest slide generator, currently expected to resolve to:

```text
gen_slides_v20.py
gen_slides_prompt_v20_hybrid.txt
```

The hybrid slide contract must retain both:

- v6/v7 source-fidelity, anti-omission, figure-matching, ordering, density, and LaTeX safeguards, and
- pri-derived pedagogical improvements such as orientation, intuition, technical bridges, equation interpretation, misconception handling, visual strategy, concept checks, and conclusion logic.

Require a successfully compiled `slides.pdf` before proceeding.

After compilation:

- verify the PDF is readable,
- count pages/slides,
- detect obvious blank/clipped/failed slides where practical,
- repair deterministic LaTeX defects rather than needlessly regenerating scientifically valid content.

## F4. Hybrid narration generation

Run the active/latest narration generator, currently expected to resolve to:

```text
gen_script_v13.py
gen_script_prompt_v8_hybrid.md
```

Require:

- exactly one narration block per slide,
- preserved slide order,
- source-grounded scientific content,
- explanatory continuity rather than isolated slide descriptions,
- TTS-friendly wording,
- `script.txt`,
- `script_tts.json` when supported by the active package.

The number of narration blocks must equal the number of slides before TTS begins.

## F5. TTS generation

Run the active/latest TTS generator, currently expected to resolve to:

```text
text_to_speech_v25.py
```

Use the shared local credential directory, not project-local secret files.

Generate one `slideN.wav` for every slide. Verify the WAV count equals the slide count before continuing.

## F6. Per-slide PDF generation and MP4 assembly

Run the active/latest per-slide PDF and video stages, currently expected to resolve to:

```text
slice_pdf_v21.py
gen_video_v22.py
```

Require:

- exactly one `slideN.pdf` for every slide during the build,
- one matching `slideN.wav` per slide,
- exact slide/audio pairing,
- final `slides.mp4`,
- H.264/AAC or the active package's documented equivalent,
- no large unintended silent tail between narration segments.

---

# G. Mandatory integrity checks before publishing a subtopic

For every subtopic, calculate and verify:

```text
slide_count == narration_block_count == wav_count == numbered_slide_pdf_count
```

Also verify:

1. `slides.pdf` exists and is non-empty.
2. `script.txt` exists and is non-empty.
3. `slides.mp4` exists, is non-empty, and can be probed/read by FFmpeg/ffprobe or an equivalent media tool.
4. MP4 video duration is reasonably consistent with the sum of WAV durations; allow only normal frame/codec rounding differences.
5. The final MP4 contains both video and audio streams.
6. Any figure files actually referenced by the final deck exist.

If these checks fail, do not publish a success state and do not perform final cleanup for that subtopic.

---

# H. Publish outputs into the original subtopic directory

Only after the staging build passes all integrity checks:

1. Copy/replace the verified final generated outputs into the original subtopic folder containing `source.pdf`.
2. Never replace `source.pdf`.
3. Preserve unrelated existing files.
4. The retained output set should include, when produced by the active package:

```text
slides.pdf
slides.tex
script.txt
script_tts.json
slides.mp4
Figure*.png / FIGURE*.png and other final mapped figure assets
relevant run logs or metadata
```

5. Do not publish package source code into every subtopic directory unless the user explicitly requests it.

Use safe replacement semantics: prepare and verify new outputs first, then replace older generated outputs. A failed new run must not destroy a previously valid slide/video set.

---

# I. Storage cleanup — mandatory after successful publication

After all required final files for a subtopic have been published and re-verified in the **original subtopic directory**, remove the following storage-heavy intermediates from that subtopic directory:

```text
crops/
pages/
slide1.pdf, slide2.pdf, ... slideN.pdf
slide1.wav, slide2.wav, ... slideN.wav
```

Use numeric matching for the numbered slide files. Do **not** accidentally match or delete:

```text
slides.pdf
slides.mp4
```

For example, `slide*.pdf` is unsafe because it can also match `slides.pdf` in some shells. Match only filenames equivalent to:

```regex
^slide\d+\.pdf$
^slide\d+\.wav$
```

Cleanup is allowed only after the final `slides.pdf`, narration, and `slides.mp4` have passed integrity checks.

The isolated staging workspace may then be deleted unless it is needed to diagnose a failure.

---

# J. Multi-subtopic execution behavior

1. Process the resolved target list in natural order.
2. Maintain an explicit status table internally for each subtopic:

```text
pending -> figures -> slides -> narration -> tts -> video -> verified -> published -> cleaned
```

3. Do not restart a successfully completed subtopic unnecessarily.
4. If Codex or the machine is interrupted, inspect existing verified outputs and staging state and resume from the earliest incomplete stage.
5. Avoid simultaneous jobs on the same machine when Docling, LaTeX, TTS, or FFmpeg resource contention could reduce reliability. Parallelize only when the machine has sufficient resources or when separate machines/workers are intentionally available.
6. For multi-PC generation against the same Gemini project, require all workers to use the same `MICROGEN_GEMINI_LANE_DIR`. Figure mapping, slide generation, narration, and LLM-assisted LaTeX repair must enter the shared Gemini lane; do not bypass the lane with direct parallel Gemini calls. Non-Gemini stages may continue in parallel on different machines. Figure mapping is request-level serialized so workers can interleave fairly without concurrent Gemini calls.
7. Prefer the version-controlled `microgen_batch.py` runner for long jobs. Its per-subchapter checkpoint must be reused on retry so completed upstream stages are not regenerated unnecessarily.
8. Treat transient Gemini `429`, `500`, `502`, `503`, `504`, `RESOURCE_EXHAUSTED`, `UNAVAILABLE`, and capacity errors as retryable and use the package's exponential-backoff helper rather than immediately marking the subtopic permanently failed.
9. Treat a Gemini `402` / depleted-prepayment-credit billing response as **non-retryable**. Let the shared circuit breaker open, release the lane, and pause Gemini stages until the billing recheck window or explicit circuit clear. Do not burn the ordinary retry budget and do not re-run already completed stages while billing is unavailable.

---

# K. Final report to the user

When all selected subtopics have been attempted, provide a concise report containing:

- code-package URL and Git commit SHA used,
- selected LLM configuration,
- source root,
- resolved target subtopics,
- success/failure for each subtopic,
- slide count for each successful subtopic,
- final MP4 path for each successful subtopic,
- video duration and file size where available,
- any automatic repairs performed,
- any dependency installations performed,
- confirmation that `crops/`, `pages/`, numbered `slideN.pdf`, and numbered `slideN.wav` were removed from successfully completed source subdirectories,
- unresolved failures requiring user intervention.

Do not claim that the run is complete until the selected target set has been checked against this report.

---

# Quick-start example

A user normally needs to change only this line:

```text
SOURCE_ROOT_DIRECTORY = "G:\My Drive\My_Textbook_Project"
```

and may leave:

```text
CODE_PACKAGE_URL = "https://github.com/tlyoon/MicroGen_AI.git"
CODE_PACKAGE_REF = "main"
LLM_MODEL = "V7_DEFAULT"
TARGET_SUBDIRECTORIES = "AUTO_FIRST_PARENT_ALL"
MICROVID_CONFIG_DIR = "AUTO"
GEMINI_LANE_DIRECTORY = "DISABLED"
WORK_ROOT_DIRECTORY = "AUTO"
```

Then submit this entire Markdown file to Codex and instruct it to **execute the workflow**, not merely summarize the prompt.

Expected behavior with a source hierarchy beginning with `1/` is to process every valid `source.pdf` under `1.1/`, `1.2/`, ..., through the last valid subtopic in that first parent folder, generate the complete slide+narration+video set for each, publish the final assets in each respective subtopic directory, and remove the specified temporary storage-heavy intermediates after successful verification.
