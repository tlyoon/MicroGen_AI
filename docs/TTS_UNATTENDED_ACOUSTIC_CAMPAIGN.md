# PR #46 — No-manual-gate end-to-end acoustic + QA command

`python microgen_tts_autonomous_campaign.py ISOLATED_LECTURE NEW_EXTERNAL_QA_FOLDER`

The command uses two independently named configured Gemini audio-recognition models on all original WAVs, verifies each original WAV and source manifest before and after recognition, builds an external PR #45 QA packet and applies the 2026-10-20 `autonomous` technical-readiness policy. There are **no human/manual gates** and no invented transcripts: model outages, credential absence, stale hashes, PCM faults or broken media produce explicit blockers. The packet is an audit result only; **no publication, original-file overwrite, voice switch, TTS regeneration or Moodle action** occurs. The user can correct newly discovered audio errors later through isolated regenerations.

`--offline` is a deliberate, non-billed diagnostic mode: it produces UNKNOWN acoustic evidence and an expected blocked release. Live recognition uses configured local keys and may incur Gemini charges. The default model IDs are configurable on the CLI. No Whisper installation.

Automated clearance is a narrowly defined technical gate, **not proof** of phonetic exactness, scholarly correctness, complete figure preservation or synchronized element highlighting. The QA packet exposes those unproven quality dimensions and keeps optional listening queue files.
