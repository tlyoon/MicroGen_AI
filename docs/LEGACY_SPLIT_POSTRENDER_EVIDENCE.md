# Legacy split post-render QA evidence adapter

MicroGen_AI. Use when an archived MP4 candidate has **two separately
verified reports**, but the modern release gate expects the independent
post-render verification nested inside video_repair_report.json.

Canonical observed case: Thomas Calculus 1.2. Historical pre-render/initial
candidate video_repair_report.json already recorded 18 original slide scenes,
source PDF/MP4 SHA256, exact preserved AAC, and corrected MP4 SHA.
A separate independent_postrender_verification.json recorded 18 corrected
candidate slide scenes, all 17 transition timings, actual preserved audio
hashes, and final corrected video SHA.

## Usage and invariants

    python microgen_legacy_split_evidence.py
      --source ORIGINAL_COURSE_SUBCHAPTER
      --archive ORIGINAL_VERIFIED_VIDEO_PILOT_FOLDER
      --output UNUSED_LOCAL_PRIVATE_CANDIDATE_DIRECTORY

The adapter refuses:
- Changed original source slides PDF or MP4.
- Changed corrected PDF or MP4 versus BOTH historic reports.
- Mismatched actual encoded AAC audio packets or missing independent
  explicit same-audio verification.
- Wrong source/candidate page count, missing scene proof, reordered scene
  or PDF page mapping, transition drift above 0.4 seconds, image pixel
  deviations greater than 11/255, or inconsistent duration.
- A preexisting output, path overlapping the original course/source, or
  an already modernized report.
- Any failure of the current strict PDF QA, media hash/timing checks,
  or complete modern technical release-readiness gate.

On success, create a NEW private, isolated candidate folder containing
byte-for-byte copies of original corrected slides PDF, MP4 and two historical
reports plus a modern report whose candidate_video_verification embeds the
old independent post-render report. The modern report explicitly pins SHA256
of both original reports and notes it neither reencoded audio/video nor
performed publication or academic signoff.

Never modify or delete the original historical audit files. Never treat
this adaptation as permission to write to a course or Moodle folder.
A separate pinned-owner campaign, two COMPLETE original snapshots,
independent pre- and post-promotion checks, and guarded explicit release
authorization remain mandatory before production release.

## Test and acceptance result

On Dell-115, the archived Thomas 1.2 candidate passed the normal
current modern release gate after isolated evidence adaptation.
- 18 slide scenes and 17 transitions validated
- Original and corrected encoded AAC streams identical
- No media re-encoding or original archive modification
- Corrected PDF SHA256:
  3a352ad3ce19c559458fc63e82d0e726c79f6ea3999b4e489678588a1f73d585
- Corrected MP4 SHA256:
  50a5a9fffda0e45d13cbefc7db71c5ac529052dc5a8293fd58a257b295448d0e
- Historical original report SHA256:
  c2e0e6e56570bb4e74b928d34c22cb31063d216dbdd37794ff6fe680f9239216
- Historical independent QA report SHA256:
  55bfbf7e72467927ba1a52838d3158ded7abbb85ca7d4645b15e19ee139ee4d6

All previously verified production MP4s remain unchanged. The 1.2
adapted output is a candidate ONLY, pending independent PC acceptance
and future controlled production promotion.
