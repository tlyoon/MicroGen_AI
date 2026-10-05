# v7 Hybrid Slide + Narration Prompt Integration v1

Date: 2026-10-04

## Purpose
Combine the strongest slide-generation and narration instructions from the v6/v7 workflow and the pri Microvid workflow without weakening source fidelity, coverage, deterministic output, or legacy v7 file compatibility.

## Active versions
- Slide generator: `gen_slides_v20.py`
- Slide master prompt: `gen_slides_prompt_v20_hybrid.txt`
- Narration generator: `gen_script_v13.py`
- Narration master prompt: `gen_script_prompt_v8_hybrid.md`

The existing `functions.get_latest_script()` mechanism automatically selects these higher-numbered generators.

## Slide-generation merge policy
V6/v7 remains authoritative for:
- exact subchapter boundary detection;
- first-valid-section selection;
- anti-omission discipline;
- `CoverageMap`, `GapList`, and `FigureMap` thinking;
- coverage of definitions, laws, examples, equations, figures, cautions, and subheadings;
- macro source order;
- exact source-figure matching;
- deterministic LaTeX Beamer output;
- density/overflow rules;
- LaTeX safety and post-generation audit.

Pri contributes:
- BigIdea / GoverningQuestion / EndCapability planning;
- substantive learner orientation rather than a thin agenda;
- intuition before or alongside formalism;
- explicit technical bridges between non-obvious equation/concept transitions;
- equation interpretation;
- source-supported misconception contrast;
- deliberate choice of visual representation;
- avoidance of unnecessary sequences of bullet-only slides;
- reasoning-based concept checks;
- conclusion that closes the intellectual loop.

## Resolved instruction conflicts
### Outline vs introduction
Use `Orientation & Roadmap` as the second slide. It preserves the v6 roadmap function while also giving the pri-style big-picture mental model and motivating question.

### Source order vs pedagogical reordering
Preserve macro source order. Local bridge, comparison, check, orientation, and recap slides may be inserted when useful, but major source units are not freely reordered.

### Source-only vs prerequisite bridging
No new domain facts, laws, assumptions, numerical examples, applications, or external figures are allowed. Directly implied algebraic, geometric, calculus, or logical bridge steps may be made explicit when they follow unambiguously from source-supported material.

### Completeness vs compression
Completeness governs. Compression may shorten wording or improve representation, but may not erase substantive source content.

### V6 summary/review vs pri check/conclusion
Use both strengths:
1. Title
2. Orientation & Roadmap
3. Concept development
4. Reasoning-based Concept Check
5. Conclusion / Summary
6. Two final Review Questions

## Narration merge policy
V7 remains authoritative for:
- exactly one narration result per fixed slide;
- no skipped, duplicated, merged, inserted, or reordered slides;
- `slides.pdf` as the visual/sequence authority;
- `source.pdf` as the subject-matter authority;
- professional university lecture tone;
- legacy `script.txt` output and one-to-one slide numbering.

Pri contributes:
- continuous reasoning across slides;
- explanation rather than slide reading;
- intellectual problem framing on the first substantive slide;
- intuition -> terminology -> formalism -> interpretation;
- equation meaning and technical bridges;
- figure/graph/table/process attention guidance;
- source-supported misconception handling;
- selective prediction and micro-recaps;
- TTS-aware speech engineering and optional `tts_text`;
- visual-inspection time and cognitive pacing;
- meaningful check and conclusion narration.

## Narration timing resolution
Actual `estimated_seconds` and configured `narration_wpm` are authoritative. The older 120-180 words-per-slide guideline is retained only when duration genuinely supports it. The hybrid prompt normally targets roughly 60-80% of theoretical speech capacity so the learner has time to inspect equations, figures, and questions.

## Compatibility
The normal v7 copier copies every file from the template into subchapter directories, so both new hybrid prompt files are propagated automatically. Existing output conventions remain unchanged: `slides.tex`, `slides.pdf`, `script.txt`, `script_tts.json`, `slideN.pdf`, `slideN.wav`, and `slides.mp4`.

## Rollback
Pre-hybrid versions are preserved under:
`_backup_before_hybrid_prompts_2026-10-04`
