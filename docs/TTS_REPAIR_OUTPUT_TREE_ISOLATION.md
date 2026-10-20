# Direct repair API: strict output-tree isolation

The existing stage-only TTS repair API must never write candidate WAVs inside the source lecture tree. Its previous guard rejected existing output directories and equal paths but could permit a **new child path under the lecture folder**. This correction canonically resolves the source and proposed output paths *before any candidate output or paid synthesis* and rejects both source descendants and source ancestors, including existing aliases. A new sibling scratch directory remains permitted.

Three new adversarial tests cover uncreated nested child paths, source ancestors, and Windows symlink aliasing (the latter may be skipped when Windows disallows creating symlinks). The source WAV's original bytes must remain unchanged. Output files remain review-only and source SHA-bound; this change does not grant publication or claim phonetic verification.
