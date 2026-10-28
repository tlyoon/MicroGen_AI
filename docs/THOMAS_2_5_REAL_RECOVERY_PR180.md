# Thomas §2.5 real Dell-115 source recovery — PR #180

Original `tlyoon/MicroGen_AI`, **not MicroGen_AI_Web**. Historical
source materials are read-only. No protected `main` merge, no source
overwrites, no HP/Yoga6/Zenbook work, no paid API, Whisper, Google Cloud
lease, Moodle or YouTube publication.

## Input lineage independently checked on Dell-115

The user's designated cloned textbook folder
`G:\My Drive\Projects\Thomas_calculus_13ed\2\2.5` contains only
`source.pdf`. Its SHA-256 is
`dbc34b5de194c3eedcfc686dfabacc903cc45d858b7a5240912a358d2f2f384b`.

The *original, separate, historical production folder* is:
`G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\2\2.5`.

An independent preserved production record dated 19 October 2026 gave:
- slides.pdf SHA-256 `775abbaee3bd54a9885894ada4b5347fdc05a0a36aa278fc8420fe5b1406bc30`;
- slides.mp4 SHA-256 `7d27d24d5d6a7ae5bf05cfcef1ea324d628abcf70688437a5555ac1c85b7e9f8`.

Both matched actual historical bytes. The source-PDF clone also matched
the production source. Historical `script_tts.json` SHA-256:
`f645222f0c2acb2a57ce038995c8152bdacc086804733f417d34ab1e64d6b56b`.
The new `microgen_section25_real_recovery.py` copies **only** these
four known source files, the authentic scene evidence, and the nine exact
historical QA WAV/receipt files, to one NEW Dell AppData-only mirror
after preflight hashes. Each original and copied SHA is verified again.
No direct writes to either G: Drive path.

## Actual completed real-media pipeline

Isolated Dell-115 campaign:
`C:\Users\tlyoon\AppData\Local\MicroGen_AI_Checkpoints\20261024_Section25_REAL_PILOT`.

Results (no synthetic fixture values are presented as real evidence):

1. **mirror:** 13 source/evidence files verified and copied, no publication.
2. **recover:** actual historic 17-page MP4 decoded to **17 original
   provisional scene WAVs**, source MP4 SHA intact, 550.23 seconds
   visual timeline; separately preserved original AAC tail is 1.023375 s
   with measured RMS 0.064126.
3. **tail:** technical lossless ALAC MP4 **551.25 seconds** with all
   551.253375 seconds of source audio preserved at exact PCM sample
   SHA-256 equality. Candidate SHA-256
   `ab7fe4120b4f4854471eb83fccc9ab2bc53c4cdd0affa150cdbe9446e39c8943`.
   This is a *nonpublishing technical master*, NOT corrected narration.
4. **review:** four source-evidence-checked historical correction
   candidates; reference slides 5, 6, 10; all UNAPPROVED.
5. **select:** exactly three unique SHA/source-bound trial WAVs selected
   for slide 5 CDOT, slide 6 CDOT and slide 10 Y_VALUE.
6. **corrected:** new 17-slide WAV stage, 14 unchanged original clips +
   3 verified selected historical correction trials; **551.686 seconds**,
   under 600 seconds, no old word cues copied. `fresh_asr_required=true`.
7. **shadow:** complete corrected trial narration with original AAC
   tail, **552.709 seconds**; `publication_allowed=false`,
   `word_cue_timing_valid=false`.

## Confirmed defect and permanent fix

- Dell-115's older pre-installed LAMMPS FFmpeg lacks video `tpad`.
  The first technical render failed. New CLI checks the filter before
  any video output rather than repeatedly trying an unsupported binary.
- An already installed imageio FFmpeg v7.1 supports `tpad`, but two
  locally installed FFmpeg AAC decoders yielded the same **8,820,054
  PCM samples** while producing different content hashes:
  - original LAMMPS decoder (used to extract scene WAVs):
    `21cc4747ef1f748134edee2696ba06cd10ac56fce6e713adbb450068ca79fe7d`;
  - v7.1 decoder:
    `f753bfd1dd8573cc3782b5069895b690c5b16d319e41225675e3177a982e8afe`.
  The original strict PCM equality gate correctly rejected the
  decoder-mismatched attempt; no false success was recorded.
- Permanent change: `render_audio_tail_candidate` optionally accepts
  an explicit `source_decoder_ffmpeg` separately from the video
  renderer. The original historical MP4 and staged WAV master must
  match **bit-for-bit using the decoder that created the WAVs**.
  Independently decode the new ALAC output and compare exact PCM
  SHA and sample count. Neither SHA, duration, source consistency,
  source overwrite nor publication checks are relaxed.
- Both executable SHA-256 fingerprints are stored in the new
  technical acceptance receipt. Failed disposable intermediate output
  was removed only from the owned Dell AppData QA stage; no historical
  file was changed.

## Limits and next acceptance unit

The Dell-115 Miniconda environment currently does **not** have optional
Vosk installed, and no authenticated local Vosk model was established.
Consequently the newly corrected 17-slide audio has **no fresh ASR-based
word cue manifest or corrected highlighted MP4**. Narrator consistency,
c-dot/y phonetic correctness, figure/equation semantics, academic
content QA and independent listening remain **unverified**.

Next recommended milestone: obtain an approved *already installed*
offline acoustic model and run PR #178 `capture`/`align` against this
verified 17-slide corrected stage; then render a new nonpublishing
technical MP4 and verify actual cue pixels and scientific content.
Do not use previous 66 original-word timestamps, synthesize evidence,
install Whisper, pay for an API, or publish without acceptance.
