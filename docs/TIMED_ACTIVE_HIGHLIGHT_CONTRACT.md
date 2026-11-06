# Measured active-element highlighting — draft engineering contract

Project scope: original Gemini-API MicroGen_AI, not MicroGen_AI_Web.

## Verified gap

The current gen_video_v22.py renders a static slide PNG for the complete slide WAV.
Previously accepted private lectures therefore do not establish narration-synchronized
within-slide highlighting. Do not infer timing from a proportional word-count
division of the whole-slide WAV, or reinterpret old private acceptance receipts
as evidence of this missing feature.

## Input manifest

The new, unmerged microgen_timed_highlight_contract.py module validates
.microgen_timed_highlights.json in an isolated stage folder.

- schema_version: 1
- timing_method: measured_ordered_pcm_chunks
- publication_allowed: false
- slides_pdf_sha256: actual full PDF hash
- script_tts_sha256: actual narration sidecar hash
- slides: all ordered slide rows, each with exact PDF and WAV hashes.
- Each slide cue has element_id, pdf_text, spoken_text, pdf_bbox (four page-point
  coordinates), audio_chunk, and audio_chunk_sha256.
- The chunk path must match highlight_chunks/slideN_cueM.wav and the correct
  slide/element order.

The source producer must synthesize each cue with the configured Gemini
Flash-Lite voice, then form the complete slide WAV from the exact ordered PCM
samples. The validator independently rechecks sample-rate/channel matching,
ordered sample-for-sample reconstruction of the whole WAV, SHA hashes, visible
PDF-text containment, script-text coverage in order, rectangle bounds and
symlink/path security. It does not use Whisper or ASR.

The returned FFmpeg drawbox filter is time-gated to measured PCM frame intervals.
It is a rendering primitive only. The current validator deliberately reports
visual_highlight_rendering_verified=false and
spoken_word_to_element_alignment_verified=false. Its result does not grant
publication rights.

## Remaining development milestones

1. Integrate the element-by-element TTS producer and PCM concatenation into
   the existing Gemini Flash-Lite pipeline with consistent voice and bounded retries.
   Do not add local models or unnecessary Google Cloud TTS dependence.
2. Wire the optional FFmpeg timed-overlay renderer into production and bind
   segment cache hashes, multipart receipts and acceptance snapshots to the cue
   manifest and its audio chunks. Existing static caches must never count as
   highlighted-video evidence.
3. Decode actual video frames before, during and after each cue, verify visual
   highlight transitions and bounded drift, and produce a separate SHA-bound
   synchronization receipt only after successful tests.
4. Keep the scientific, math, figure, pronunciation, <600-second video and rights
   gates independently enforced; no fabricated coverage claims or publication.

Device: Dell-115 only for the current validation contract. If unavailable,
preserve this as a GitHub draft, report unverified code accurately and
continue other independent authorized work. Do not repeat failed Serway 8.2
PDF-specific repairs.

Release tracker: https://github.com/tlyoon/MicroGen_AI/issues/278
