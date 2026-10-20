# PR #37 — Bounded PCM audio integrity QA

A syntactically valid WAV can still contain silence, severe clipping, pathological padding, or an implausibly brief non-speech recording. The new `microgen_tts_wave_integrity.py` analyzer streams 16-bit mono PCM in small blocks, recording level, peak, clipping fraction, leading/trailing quiet, samples and duration without materializing full textbook audio as a list.

Severe digital silence, over 5% clipped samples, invalid PCM or duration under 0.08 seconds **blocks** bounded TTS repair candidate acceptance. Very low level and large quiet padding yield review warnings, never fictional pronunciation clearance. Thresholds are conservative and require real-world calibration on spoken audio. The existing PR #31 repair stage binds quality evidence into each attempt receipt. This is structural acoustic QA, not a replacement for script-blind recognition, mathematical pronunciation detection, human listening or release approval.
