# PR #33 — Harden independent acoustic evidence before release

This PR closes a fail-open gap in the earlier read-only release audit: matching slide numbers and WAV hashes are insufficient to prove that acoustic recognition was actually performed. The audit now cross-checks two *different* named recognition models, two nonempty script-blind transcripts per slide, the SHA-256 of the precise normalized spoken input, complete per-slide audio hashes, internally consistent review-required summaries and the original voice-provenance receipt.

Every claimed comparison is independently recomputed from the transcript and expected text. Declared zero mismatch with audibly recognized `yay` instead of `why`, any new mispronunciation word, or a missing transcript invalidates the acoustic screen. A valid acoustic screen cannot assert human listening approval. Existing human, academic, figure and element-highlight review and strict video duration gates remain independently required.

The historical Thomas Calculus §2.5 pilot stays **not publishable** because real verified acoustic evidence and complete review receipts are missing. This module neither invokes model APIs nor alters original audio. Reviewer receipt authenticity must also be checked by the separate publication authority, beyond the read-only content validator.
