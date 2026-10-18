# MicroGen_AI: backup-first release of legacy visual repairs

Date: 18 October 2026. Applies to MicroGen_AI, not MicroGen_AI_Web.

## Preserve the receipt contract

The existing v1 .microgen_verified_completion.json requires a full set of
per-slide WAV hashes and TTS timing. Many historic Thomas lectures do not
have those WAVs. Never fabricate WAV evidence or treat a video-only repair
as a newly generated lecture. No v1 receipt validator was changed.

The new, distinct v2 marker is .microgen_legacy_visual_repair_receipt.json.
It cryptographically binds the original source PDF, original slides PDF/MP4,
narration script/sidecar, figures, corrected PDF/MP4, unchanged AAC stream,
corrected post-render scene/timing evidence, and explicit WAV-provenance
limitations. It does not claim independently signed academic review.

## Stage 1: prepare a local package, NOT production publishing

The default operation of microgen_legacy_promotion.py is --prepare (implicit).
Run from an approved clean local checkout with a unique local package path.

Example argument list for 2.2:

    python microgen_legacy_promotion.py
      --course "G:\My Drive\ZCA110_2627_SEM1\MCQ_generation\Thomas_calculus_13ed\2\2.2"
      --section 2.2
      --candidate "G:\My Drive\MicroGen_Experimental_Review_20261016\Video_Batch_Coordination\pilot_fixed_owner_20261017\candidate_2_2"
      --package "%LOCALAPPDATA%\MicroGen_ReleasePreparation_20261018\2_2_NEW"
      --pdf-sha256 9fd2661c755ed0ba69d66717db65a40845bb8d6454b297165df1360c091580d4

The example splits arguments for readability. Join into one shell command,
or use normal PowerShell line continuation in your own terminal.

The new package contains:
- original/: a hash-verified complete copy of the prior course folder,
  including scripts, figures, Moodle XML/HTML, source.pdf, slides.pdf and MP4.
- candidate/: verified corrected PDF/MP4, v2 receipt, video QA evidence.
- package_manifest.json: pinned hashes; state PREPARED_NOT_PUBLISHED.

No production output is replaced. A pre-existing package path is refused.

## Stage 2: secondary, independently audited backup

Before any course replacement, mirror the package to a protected independent
Drive location, verify all file hashes and have a SECOND PC independently
verify the backup and current original course files.

Actual 2.2 test copies:
Primary: %LOCALAPPDATA%\MicroGen_ReleasePreparation_20261018\2_2_v2
Private second copy:
G:\My Drive\MicroGen_Experimental_Review_20261016\Legacy_Release_Preparation_20261018\2_2_v2

HP independently verified the 16 original source files, their protected
backup counterparts, and all staged candidate media/receipt/evidence hashes.
No source file was modified.

Read-only audit command:

    python microgen_legacy_promotion_audit.py --course COURSE_FOLDER --package PRIVATE_BACKUP_ROOT

## Stage 3: production transaction — NOT executed by this development

The --promote mode requires a separately explicit single-bundle production
authorization, a clean SHA-pinned code checkout, an immutable Drive-native
one-PC owner, an unchanged original full-file inventory, and TWO independently
verified complete backups.

It stages corrected slides.pdf, slides.mp4, the QA evidence, and v2 receipt on
the destination filesystem, verifying hashes. It replaces ONLY those files,
writes the new marker last, and revalidates the result. Any failure triggers
rollback to the original snapshot and verifies the complete original inventory.
If rollback itself fails, it writes CRITICAL_ROLLBACK_FAILED and stops.

A successful transaction remains flagged:
PROMOTED_AWAITING_SECOND_PC_DESTINATION_VERIFICATION.
It does not grant Moodle publication or academic signoff.

## Stage 4: independent post-publication technical audit

On a different authorized PC:

    python microgen_legacy_promotion_audit.py --destination-audit --course COURSE_FOLDER --package SECOND_BACKUP_ROOT --pdf-sha256 PINNED_PDF_SHA --mp4-sha256 PINNED_MP4_SHA --receipt-sha256 PINNED_RECEIPT_SHA

The audit proves the original figure, script and Moodle files are unchanged;
only the corrected PDF, MP4, evidence and receipt have changed. The AAC
identity, scene/timing report, matched original backups and current media
are checked. It is a technical audit only.

## Exclusions and operating contract

1.1: 17 slides but 22 stale WAVs.
3.2: original video scene mismatches the source slides.
5.6 and 7.2: truncated title narration; coordinated TTS/audio/video needed.
3.3, 3.10, 4.2, 4.6, 4.8: unresolved mathematical overflow/reflow.
Existing v1 completion receipts: reject rather than silently replace.

Never use Zenbook. Do not use Google Cloud Storage leases. Drive-native fixed
owner manifests and local per-PC FIFO remain the coordination contract.
Do not auto-reassign disconnected workers. Academic approval is assumed at
the user's direction; no separate signed human review is invented.
