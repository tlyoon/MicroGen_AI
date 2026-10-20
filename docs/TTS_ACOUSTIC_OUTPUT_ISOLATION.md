# PR #42 Acoustic evidence output isolation

The independent Gemini audio audit must write a NEW result JSON **outside** the source lecture tree, never next to the original WAVs. Use `python microgen_tts_acoustic_qa.py STAGED_LECTURE --new-report NEW_EXTERNAL_REPORT.json`. The destination and existing-file collision are validated before network/audio model requests; reports use exclusive-create writes rather than an overwrite-capable replace. All original sources remain read-only.

This does not eliminate genuine acoustic blockers, authorize Moodle publication, or automatically sign human review. Under the 2026-10-20 autonomous contract, manual review is optional, and independent acoustic screening remains a technical requirement. No Whisper.
