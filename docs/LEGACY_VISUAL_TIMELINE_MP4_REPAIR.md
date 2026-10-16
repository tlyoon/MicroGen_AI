# Legacy MicroGen_AI — MP4 slide repair using original visual timing

This procedure upgrades the *visual slide pages* in a legacy lecture MP4 without
regenerating narration or changing production lecture files. It does not
publish anything, authorize Moodle publication or invent a signed reviewer
record.

## Why WAV duration cannot be assumed to be video timing

Thomas 1.1 has 17 PDF slides and narration entries, but 22 stale numbered
WAVs. The tool detects this mismatch and refuses repair.

Thomas 1.2 has 18 PDF slides, 18 narration entries and 18 numbered WAVs.
Its WAV duration totals about 541 seconds, while the published MP4 lasts
591.1 seconds. The repair procedure determines slide changes from the
original *MP4 pixels*, not from the WAV duration estimate.

## Procedure

On the PC running a clean LOCAL DISK checkout of MicroGen_AI:

    $code = Join-Path $env:LOCALAPPDATA 'MicroGen_AI'
    $src = 'G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\1\1.2'
    $pdf = Join-Path $env:LOCALAPPDATA 'MicroGen_RepairCandidates\1_2\slides.pdf'
    $out = Join-Path $env:LOCALAPPDATA 'MicroGen_VideoCandidates\1_2'
    python (Join-Path $code 'microgen_legacy_video_repair.py') --source $src --corrected-pdf $pdf --output $out

The corrected PDF must first pass microgen_legacy_pdf_repair.py. The
output directory **must not already exist** and must not be on a
synchronized cloud drive.

## Fail-closed verification stages

1. Verify corrected slide PDF has the same page count, original visible
   mathematical words, and original embedded images.
2. Check narration slide indices and numbered WAV counts for stale inputs.
   Do not derive timing from them.
3. Detect N-1 actual original scene transitions for N original PDF slides
   at 5 Hz. Fail on extra, missing or ambiguous changes.
4. Validate an interior video screenshot against each original PDF page;
   the best visual match must be the corresponding page and its pixel
   error must be below threshold.
5. Render the corrected PDF pages at the original transition timestamps.
   Remux the original AAC stream with FFmpeg codec-copy; do not synthesize,
   speed-shift, resample or replace the narration.
6. Compare exact SHA-256 of the old and new copied AAC streams. Verify
   video/audio streams and the total video duration.
7. Independently inspect the newly generated candidate MP4, re-detect
   all its transitions and compare their timings with the original
   (maximum permitted shift 0.4 second). Match all rendered scenes to
   the corrected PDF pages.
8. Check that the source PDFs, original MP4 and corrected PDF have not
   changed during processing. Save an audit report.
9. Never overwrite production lectures or create a hash-bound completion
   receipt. Rejected trials stay in isolated failed scratch directories.

This is a static-slide repair for **MicroGen_AI**. It does not implement
the word- or element-highlighting requirements of the separate
MicroGen_AI_Web project.

## Actual 18-slide Thomas 1.2 pilot (October 16, 2026)

- Original video: 591.1 seconds.
- Exactly 17 original scene boundaries were recovered at 5 Hz.
- All 18 original frames matched corresponding original PDF pages.
- All 18 corrected MP4 frames matched corresponding repaired PDF pages.
- Maximum corrected frame mean absolute pixel error: 3.401 / 255.
- New transition offsets compared to originals: 17 values of 0.0 seconds
  at the 0.2-second analysis resolution.
- Original and candidate audio stream SHA-256 were identical:
  5d3ec5dac55dffbd9213994394376f556be4bc1595083fab36681db47595b155
- Output was a locally staged PASS candidate; **not published**.

## Follow-on release gate

Before promoting anything into the ZCA110 course tree, back up the full
original destination, verify the PDF/video/narration bundle and required
media, create a genuine source-bound completion receipt, and independently
verify the destination on another PC.

The user explicitly instructed the team to assume independent academic
approval; that statement does not create a fictional signed per-file
academic certificate.

Overflow sections 3.3, 3.10, 4.2, 4.6 and 4.8 still need safer
mathematical layout repairs. Section 5.6 and 7.2 narration introductions
remain truncated and need coordinated TTS/media correction rather than
visual-only remuxing.
