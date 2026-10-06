# MicroGen_AI

MicroGen_AI is an AI-assisted educational media generation toolkit developed for producing source-grounded teaching materials from a textbook or course PDF. The current package combines the strongest parts of the earlier v6/v7 workflow with the improved pedagogical and media-generation ideas developed in the newer `pri` pipeline.

The main workflow converts a `source.pdf` into extracted textbook figures, LaTeX Beamer slides, slide-by-slide narration, Google Cloud text-to-speech audio, per-slide PDF/WAV assets, and a final narrated MP4 video.

## Design goals

MicroGen_AI is built around two complementary priorities:

- **Source fidelity and completeness.** The v6/v7 lineage contributes strict subchapter isolation, source-order preservation, anti-omission checks, figure matching, deterministic output conventions, and LaTeX robustness.
- **Pedagogical quality.** The newer hybrid instructions add learner orientation, big-picture framing, intuition before formalism, explicit technical bridges, equation interpretation, misconception handling, reasoning checks, visual teaching strategy, and continuous narration across slides.

The result is intended to behave like a reproducible educational production pipeline rather than a generic slide-generation prompt.

## Current active pipeline

```text
source.pdf
   |
   +--> Figure abstraction
   |      crop_figs_v3.py
   |      map_and_rename_v5.py
   |      merge_lettered_figs_v2.py
   |
   +--> Hybrid slide generation
   |      gen_slides_v20.py
   |      gen_slides_prompt_v20_hybrid.txt
   |
   +--> Hybrid narration
   |      gen_script_v13.py
   |      gen_script_prompt_v8_hybrid.md
   |      narration_polish.md
   |      system_microcredential_architect.md
   |
   +--> TTS
   |      text_to_speech_v25.py
   |
   +--> Per-slide PDF generation
   |      slice_pdf_v21.py
   |
   +--> MP4 assembly
          gen_video_v22.py
          FFmpeg
```

`functions.py` resolves versioned modules automatically and selects the highest available `*_vNN.py` implementation for each pipeline stage.

## Principal outputs

A completed run normally produces:

```text
pages/                  page-level extraction workspace
crops/                  retained image crops
Figure *.png             mapped textbook figures
slides.tex               generated Beamer source
slides.pdf               complete slide deck
script.txt               v7-compatible narration text
script_tts.json          narration/TTS sidecar
slide1.pdf ...            individual slide PDFs
slide1.wav ...            individual narration audio
slides.mp4               final narrated video
```

Generated artifacts are intentionally excluded from version control by `.gitignore`.

## Main entry points

For a full source-to-video run:

```powershell
python run_gen_slides_videos.py
```

This orchestrates the existing v7 stages:

```text
run_gen_slides.py
  -> image abstraction
  -> hybrid slide generation

run_gen_video.py
  -> hybrid narration
  -> text-to-speech
  -> slide splitting
  -> MP4 generation
```

For staged execution, the two commands can also be run separately:

```powershell
python run_gen_slides.py
python run_gen_video.py
```

## Installation

MicroGen_AI is currently Windows-first and has been used with Windows 11, Python 3.11/3.12, MiKTeX and FFmpeg.

### 1. Create an environment

```powershell
conda create -n microgen_ai python=3.11
conda activate microgen_ai
pip install -r requirements.txt
```

### 2. Install LaTeX and FFmpeg

Install a LaTeX distribution that provides `pdflatex` (MiKTeX is currently used in production).

Install FFmpeg or install `imageio-ffmpeg`. The video stage resolves FFmpeg in this order:

1. `MICROVID_FFMPEG`
2. packaged `imageio-ffmpeg`
3. system `PATH`

### 3. Figure abstraction dependencies

`crop_figs_v3.py` uses Docling and `pdf2image` for textbook figure extraction. Docling can be dependency-sensitive, so a dedicated environment is sometimes preferable.

Typical additional packages are:

```powershell
pip install docling pdf2image pillow
```

On Windows, `pdf2image` also requires Poppler to be installed and available on `PATH`.

The figure-size threshold `ikB` in `crop_figs_v3.py` may need to be adjusted for a textbook family. For example, Thomas' Calculus 13th edition has been run successfully with a threshold around 4.0 kB.

## Default Gemini model

MicroGen_AI now uses **Gemini 3.1 Pro Preview** as the package-wide default LLM for the active figure-mapping, slide-generation, and narration stages:

```text
gemini-3.1-pro-preview
```

This model ID is the current Gemini API endpoint for Gemini 3.1 Pro. The default can be overridden globally with `MICROGEN_LLM_MODEL` or per stage with `MICROVID_FIGURE_MODEL`, `MICROVID_SLIDE_MODEL`, and `MICROVID_NARRATION_MODEL`. If no override is supplied, the package uses `gemini-3.1-pro-preview`.

## Multi-PC Gemini coordination

When several computers generate subchapters against the same Gemini project, do not let the Gemini-heavy stages run independently. MicroGen_AI now includes `gemini_lane.py`, a cooperative FIFO lane that serializes figure mapping, slide generation, and narration across participating machines while still allowing Docling extraction, LaTeX compilation, Google Cloud TTS, PDF slicing, and FFmpeg work to proceed independently.

Enable the lane by setting the same synced directory on every worker, for example on machines that share the same Google Drive mount:

```text
MICROGEN_GEMINI_LANE_DIR=G:\My Drive\MicroGen_AI\coordination\gemini_lane
```

The lane uses queue tickets, a synchronization settling window, a heartbeat, stale-ticket recovery, and a post-request cooldown. It also tolerates short Google Drive/Desktop mount interruptions by waiting for the shared lane path to reappear instead of immediately failing the subchapter. Gemini requests use conservative exponential backoff for transient `429`, `500`, `502`, `503`, `504`, `RESOURCE_EXHAUSTED`, `UNAVAILABLE`, and related capacity errors. Useful tuning variables are `MICROGEN_GEMINI_LANE_SETTLE_SECONDS`, `MICROGEN_GEMINI_LANE_CLAIM_GRACE_SECONDS`, `MICROGEN_GEMINI_LANE_COOLDOWN_SECONDS`, `MICROGEN_GEMINI_LANE_STALE_SECONDS`, `MICROGEN_GEMINI_MAX_RETRIES`, `MICROGEN_GEMINI_BACKOFF_BASE_SECONDS`, and `MICROGEN_GEMINI_BACKOFF_MAX_SECONDS`.

For a single-PC run, leave `MICROGEN_GEMINI_LANE_DIR` unset and the coordination layer is disabled. For multi-PC work, every participating machine must point it at the same shared directory; otherwise the workers are not in the same lane.

## Credentials

Credentials are deliberately kept outside the repository.

By default MicroGen_AI reads shared API configuration from:

```text
%LOCALAPPDATA%\Microvid\
```

The default files are:

```text
%LOCALAPPDATA%\Microvid\.env
%LOCALAPPDATA%\Microvid\google_cloud_credentials.json
```

A minimal `.env` is:

```text
GEMINI_API_KEY=your_key_here
```

Optional legacy providers may also use:

```text
OPENAI_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
```

The credential directory can be overridden with:

```text
MICROVID_CONFIG_DIR
```

For Google Cloud TTS, `GOOGLE_APPLICATION_CREDENTIALS` takes precedence when explicitly set.

**Never commit real API keys or Google Cloud service-account JSON files.**

## Quick start

Clone the repository and place a source PDF in the project directory:

```powershell
git clone https://github.com/tlyoon/MicroGen_AI.git
cd MicroGen_AI
Copy-Item C:\path\to\your\source.pdf .\source.pdf
```

Then run:

```powershell
python run_gen_slides_videos.py
```

The package writes the generated outputs into the current working directory.

## Codex batch-generation prompt

For automated multi-subtopic production on a local PC, use:

[`prompts/CODEX_Textbook_to_Video_Lecture_Set_Prompt.md`](prompts/CODEX_Textbook_to_Video_Lecture_Set_Prompt.md)

This prompt is designed to be submitted directly to Codex. Normally the user only needs to define the local `SOURCE_ROOT_DIRECTORY`. By default it:

- pulls the current `main` branch of this repository,
- installs missing Python and external dependencies when possible,
- uses the v7/hybrid model defaults,
- selects all valid `source.pdf` subtopics under the first top-level source folder,
- runs figure abstraction, slides, narration, TTS, and MP4 generation,
- publishes verified outputs back into each source subtopic directory, and
- removes `pages/`, `crops/`, numbered `slideN.pdf`, and numbered `slideN.wav` intermediates after successful verification to reduce storage use.

The prompt also accepts explicit subtopic ranges, an alternate code-package URL/ref, and a common LLM override. The historical Drive template is retained in the prompt as a fallback location, while GitHub `main` is the default authoritative package source.

### Runtime LLM override

Leaving the Codex prompt at `LLM_MODEL = V7_DEFAULT` preserves the package's stage-specific defaults. To use one explicit model for the active Gemini stages during a run, set:

```text
MICROGEN_LLM_MODEL=<model-name>
```

Stage-specific variables such as `MICROVID_SLIDE_MODEL`, `MICROVID_FIGURE_MODEL`, and `MICROVID_NARRATION_MODEL` take precedence when deliberately supplied.

## Hybrid slide-generation approach

The current slide-generation prompt intentionally merges two instruction systems rather than replacing one with the other.

The v6/v7 framework remains authoritative for:

- source isolation and content coverage
- macro source order
- anti-omission checks
- figure identity and provenance
- LaTeX/Beamer validity
- density and overflow control
- deterministic output structure

The newer pedagogical layer adds:

- an Orientation & Roadmap rather than a purely administrative outline
- an explicit big idea and governing question
- intuitive framing before formal derivation
- technical bridge explanations between compressed reasoning steps
- interpretation of equations, not just display of equations
- source-supported misconception handling
- deliberate visual-representation choices
- reasoning-based concept checks
- a conclusion that reconnects formalism to the motivating idea

Major source units are not freely reordered. The system may insert local bridge, comparison, concept-check or figure-focus slides where they improve understanding without changing the source's substantive sequence.

## Hybrid narration approach

Narration preserves the v7 requirement of exactly one narration block per slide while using the stronger `pri`-style teaching logic.

The narration stage therefore aims to:

- remain grounded in `source.pdf`
- correspond exactly to the fixed slide order
- explain rather than merely read the slide
- connect slides into a continuous lesson
- interpret equations in spoken language
- direct attention to important features of figures
- make hidden reasoning steps explicit
- produce TTS-friendly `tts_text`

`script.txt` remains the v7-compatible human-readable output, while `script_tts.json` preserves structured narration and TTS-specific wording.

## Video generation

The current MP4 stage uses a pri-derived FFmpeg workflow adapted to v7's PDF-based slides:

```text
slideN.pdf + slideN.wav
        -> rendered PNG
        -> H.264/AAC segment
        -> exact narration-duration constraint
        -> FFmpeg concat
        -> slides.mp4
```

Each segment duration is derived from the WAV sample count, avoiding the multi-second timing drift observed with older `-shortest` behavior on some FFmpeg versions.

## Repository contents

This repository intentionally contains both the active hybrid pipeline and selected legacy utilities from the v7 package. Some older modules remain for compatibility, rollback, MCQ/XML workflows, and historical utility functions.

The active versions for the main video workflow are currently:

- `map_and_rename_v5.py`
- `gen_slides_v20.py`
- `gen_script_v13.py`
- `text_to_speech_v25.py`
- `slice_pdf_v21.py`
- `gen_video_v22.py`

## Security and source-material policy

This repository does **not** include textbook `source.pdf` files, generated textbook figures, finished videos, or credentials.

Users are responsible for ensuring that any source material processed with MicroGen_AI is used in accordance with applicable copyright, licensing, institutional and privacy requirements.

## Status

MicroGen_AI is an actively evolving teaching/research automation package. The pipeline has been exercised on real university-level textbook subchapters and is being hardened through production runs. Some legacy scripts are less standardized than the current hybrid video workflow.

## Author

**Yoon Tiem Leong**  
School of Physics  
Universiti Sains Malaysia (USM)

## License

Released under the MIT License. See `LICENSE`.
