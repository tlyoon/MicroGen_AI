# Offline lecturer review package

**Purpose:** Preserve a convenient, private review environment for the lecturer to
inspect the generated material and listen to the synthesized narration **later**.
This is distinct from automatic technical verification or academic approval.

## Generate from an already verified bundle

From the local MicroGen_AI checkout:

```powershell
python microgen_review_pack.py `
  --source "G:\My Drive\Projects\Thomas_calculus_13ed\8\8.4" `
  --output "G:\My Drive\MicroGen_Experimental_Review_20261016\Lecturer_Packets\8_4" `
  --edition published
```

To inspect a corrected candidate that **has not** yet replaced the assigned
PC's original published output, set `--source` to that verified candidate and
`--edition qa-candidate`. Do not pretend a candidate is published.

Verify an existing reviewer packet independently (without requesting any original
lecture files or cloud API):

```powershell
python microgen_review_pack.py --verify "G:\My Drive\MicroGen_Experimental_Review_20261016\Lecturer_Review_Packets\8_4"
```

The command checks the package's own media/preview SHA-256 inventory and
source/video provenance hashes. It reports integrity, **not** lecturer approval.

The source bundle must have an existing, valid
`.microgen_verified_completion.json` with matching PDFs, WAVs and MP4 hashes.
The output folder must **not exist** beforehand and cannot be nested inside the
lecture source. This guards against overwriting production work. If the media
changes while a packet is being constructed, construction fails and discards
the incomplete packet.

## What the packet contains

- `index.html`: standalone offline page with full MP4 playback, one slide
  preview per page, each slide's written narration, separate TTS pronunciation
  text when different, and an individual WAV audio player.
- Approximate seek-from-slide buttons using cumulative **measured WAV**
  durations (not invented speech timings).
- Previews of **every original textbook source page**, together with a
  private copy of `source.pdf` for a reader to check context and equations.
- Textual warnings from the completion receipt for narrow figures and
  extracted but unmapped source crops.
- An **advisory** when MP4 duration is 10 minutes or longer. Different
  MicroGen projects may have different per-video length contracts; the
  reviewer determines which applies. The reviewer package does not split
  or regenerate the original video.
- `REVIEW_CHECKLIST.md`: editable tick-box checklist per slide.
- `review_inventory.json`: input hashes, source count, slide details and
  recorded warnings.
- `review_pack_manifest.json`: SHA-256 hashes of all copied/generated review
  assets for portable integrity checks.

Check boxes and comments on the offline page are locally remembered by the
browser when permitted. **Export review JSON** saves a portable draft. The
import control will refuse findings from a different source or MP4 hash,
protecting against accidental carryover between revisions.

## Limitations and safeguards

This package is a private offline copy and may contain copyrighted textbook
pages: store it only in approved private locations and do not publicly share
the folder. It does not use an external web service, make Gemini requests,
regenerate TTS, or alter source PDFs, lecture slides or published MP4s.

The status remains **NOT_REVIEWED** regardless of any checked boxes. An export
is labelled **DRAFT_UNAPPROVED**. The tool never adds a lecturer approval token
or authorizes Moodle/student publication. Human scientific and pronunciation
review remains the lecturer's independent decision.

A video seek button moves to the cumulative WAV offset, which is an
approximation for MP4 playback; small differences can occur due to encoded
audio padding and concatenation. Use the per-slide WAV player for precise
narration review.

The packet does not claim every source-page-to-slide relationship is known:
it shows the entire source page gallery rather than fabricate a mapping.
