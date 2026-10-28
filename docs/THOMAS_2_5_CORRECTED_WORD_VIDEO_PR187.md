# PR #187 — Corrected word-highlight technical video from fresh offline ASR

**Selected code:** original `tlyoon/MicroGen_AI`, stacked on latest live draft PR #186 head `a2ea0a5f632eeed1c799acc5a8e4431140b3f913`. GitHub-hosted 4/4 CI for #186 SUCCESS. Work executed on **Dell-115 only**, in isolated checkout `C:\Users\tlyoon\AppData\Local\MicroGen_AI_Checkpoints\20261025_pr187_highlight_corrected`. No HP, Yoga6, Zenbook, Whisper, paid TTS/ASR, protected main merge or publication.

## Actual Thomas Calculus §2.5 pilot

- Source: SHA-bound historical 17-slide `slides.pdf`, real corrected 17-WAV stage with 3 selected unapproved speech revisions, *full* 552.709-s corrected shadow PCM including original 1.023375-s source audio tail, and freshly decoded 17/17 Vosk slide observations from PR #186.
- `microgen_corrected_word_video.py` explicitly rejects historical/old cue schemas; accepts only the v2 SHA/audio-bound current ASR derivation from the same 17 WAVs, validates PDF geometry and all global/local clocks, then streams PDF-derived 960x540 frames at 8fps through FFmpeg. A translucent rectangle indicates the currently active recognized PDF word; no guessed highlight state persists after its ASR interval.
- Actual new **nonpublishing** technical MP4:
  `C:\Users\tlyoon\AppData\Local\MicroGen_AI_Checkpoints\20261024_Section25_REAL_PILOT\corrected_asr_word_video_v1\section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4`.
- Measured video duration **552.75 seconds** (strictly under 600); all 17 PDF slides represented, **66 current source-bound word-cue candidates**, 384 encoded frames with one or more cue rectangle(s). Independent decoded ALAC audio matches *every* corrected 16kHz PCM sample in the 552.709-second complete shadow WAV, including original tail. The previous no-highlight video, original source MP4/PDF, lecture WAV files and review packet remain unchanged.
- An independent one-frame Dell screenshot spot check at **2.595 seconds**, PDF word `continuity` on slide 1, showed mean RGB absolute difference **53.83** inside the expected word-box region and **0.047** in an unrelated bottom strip (values on a 0–255 scale). This establishes only that an actual single encoded overlay is visible, not whole-lecture or semantic quality.
- The new video receipt `word_highlight_candidate_receipt.json` deliberately records `word_highlight_pixels_independently_verified=false`, `phonetic_correctness_verified=false`, `mathematical_figure_semantics_verified=false`, `voice_consistency_verified=false`, `publication_allowed=false`.

## QA and next dependency

- New adversarial tests reject old cue derivation, forged publication flags, corrupt corrected WAVs, changed ASR source bindings, malformed PDF boxes, and output collisions. Tests exercise a synthetic full-slide renderer with mocked FFmpeg and exact PCM verification; do not substitute mocks for the real pilot evidence.
- Must still conduct **independent, comprehensive word-overlay pixel QA** on all cue instances and include tests for no-highlight intervals, PDF source fidelity and cue boundaries. The chosen PDF word is not necessarily the semantically intended math or figure element. The `c` and `y-value` pronunciations and narrator identity remain unverified by listening/phonetics. Explicit owner QA is still required for publication.
- Next best milestone: PR #188 independent real-source matched video word-cue ROI/pixel/timing audit with conservative threshold and fail-closed cross-stage source/PCM fingerprints; only when proven should an independent QA reviewer inspect mathematical figure/equation association.
