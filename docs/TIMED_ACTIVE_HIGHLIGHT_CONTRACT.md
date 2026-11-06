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

The FFmpeg drawbox filter is time-gated to measured PCM frame intervals.
The optional production path in gen_video_v22.py now renders measured cues at
10 fps when a fully validated manifest exists. The legacy static renderer
remains the default without a manifest. Timed fragments use a separate
manifest-hash-bound cache; video-part and private acceptance inputs include
the cue-chunk SHA hashes. Legacy multipart delivery is blocked for timed cues
until it has equivalent verification.

Dell-115 synthetic FFmpeg testing independently decoded the first and second
cue intervals and confirmed a visible yellow highlight switched between the
two source-grounded text regions. This verifies the overlay primitive on a
controlled example. It does NOT prove cue generation or synchronization on
a real lecture. The validator deliberately reports
visual_highlight_rendering_verified=false and
spoken_word_to_element_alignment_verified=false. No new rights are granted.

## Remaining development milestones

1. Integrate the element-by-element TTS producer and PCM concatenation into
   the existing Gemini Flash-Lite pipeline with consistent voice and bounded
   retries. Preserve the voice, pronunciation and independent acoustic gates.
   Do not add local models or unnecessary Google Cloud TTS dependence.
2. Independently decode actual MP4 frames before, during and after each cue,
   verifying the correct highlighted source region, temporal accuracy and drift
   with a SHA-bound synchronization receipt. The synthetic integration probe
   must be extended to an entire real lecture, not treated as that receipt.
3. Require that synchronization receipt at the final publication-readiness gate
   when the feature becomes mandatory. Do not retroactively reinterpret the
   existing private technical acceptance for old static lectures.
4. Keep scientific, math, figure, pronunciation, <600-second video and rights
   gates independently enforced; no fabricated coverage claims or publication.

Device: Dell-115 only for the current validation contract. If unavailable,
preserve this as a GitHub draft, report unverified code accurately and
continue other independent authorized work. Do not repeat failed Serway 8.2
PDF-specific repairs.

Release tracker: https://github.com/tlyoon/MicroGen_AI/issues/278
