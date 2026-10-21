# MicroGen_AI — latest continuation checkpoint (2026-10-21, PR #62)

## Scope and contract
This refers ONLY to tlyoon/MicroGen_AI (original), not MicroGen_AI_Web. Inspect the newest LIVE GitHub draft PR stack before development. PRs #58 through #62 are five sequential DRAFT PRs stacked on #57. Isolated Dell-115 checkout only; original source narration, PDF, WAV, MP4, source folders, dirty working trees, protected main and older draft branches must remain untouched. Under the October 20, 2026 contract, no mandatory manual gates for development or technical QA. Technical integrity/acoustic outages remain blockers. No Whisper, external GCS distributed lease or auto-publication to Moodle. Preserve each video strictly under 600 seconds and continue automated text/element-highlight QA improvements. Do not infer academic QA from technical tests.

## Actual acoustics (verified reference files)
Thomas Calculus §2.5 slide 10 faulty WAV SHA-256 74dd31f9c681eaf39ed31807f319c065350bbf9753a438829a6a47f5e8d70377 (33.145333 s); corrected WAV SHA-256 fefad11722659354750580bbf73f578281bab96c7803de0328599a3d2f5af5c8 (32.905333 s). The lecturer had listened and confirmed the corrected WHY case. Gemini transcription model normalized both defective and corrected recordings to y-value; contrastive audio judgements by Gemini 3.5/3.6 yielded UNKNOWN for all four, and no qualified audio model pair exists.

## Advances #58–#62
#58 portable SHA-bound mono PCM16 signal envelopes, RMS/silence/clipping.
#59 bounded gain-normalized time-envelope lag estimator and abstention on low correlation.
#60 portable zero-crossing and PCM-step texture measurements.
#61 bounded candidate divergence windows only when alignment is sufficiently similar.
#62 CLI for read-only, exact-hash-pinned diagnostic reports outside the source folder.

The actual original vs corrected Slide 10 wave envelopes match poorly (best correlation 0.290544). Therefore #59 reports LOW_SIMILARITY_UNALIGNABLE; #61 and #62 report ABSTAIN_INSUFFICIENT_ALIGNMENT with ZERO word/phoneme hotspot claims. Signal differences do not constitute verified mispronunciations or demonstrate an error-free detector. No PR in this sequence deploys a real phoneme-sensitive recognizer, changes publication readiness or regenerates production videos.

## Next scientific development task
Collect genuinely isolated manually labeled *time ranges* (or trustworthy phonetic alignment from an independently validated automated procedure), establish enough held-out labeled samples, test acoustic discriminators with blind evaluations. Consider small efficient DSP libraries only when justified and reproducible on Dell-115. In parallel, reconcile the large stacked draft PR chain safely before merging into protected main. No artificial or synthetic-only model qualification.
