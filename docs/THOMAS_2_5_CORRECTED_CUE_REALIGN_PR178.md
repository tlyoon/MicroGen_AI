# Thomas §2.5: regenerate audio-bound cue observations after correction (PR #178)

This new isolated Dell-115 code path addresses the *positive* recovery action missing
after PR #177's stale-cue rejection. The original MicroGen_AI package is used,
not MicroGen_AI_Web. No existing G: lecture media, protected main, YouTube or
Moodle files are modified.

## Workflow

1. Stage all actual 17 slide WAVs (original and verified correction trials) in
   an independently source-verified workspace. Rebuild the audio inventory and
   measured timeline. Do not copy any preexisting `cues.json`.
2. With the optional Vosk model **already installed locally**, execute:
   `python microgen_corrected_cue_realign.py capture --stage STAGE --model MODEL_DIR --ffmpeg FFMPEG_EXE --out NEW_ASR_REPORT.json`
   This does not download a model, call Gemini/Google Cloud, or install Whisper.
3. Execute:
   `python microgen_corrected_cue_realign.py align --stage STAGE --recognition NEW_ASR_REPORT.json`
   Only exact source-PDF/script and all WAV SHA + duration identities pass;
   an unchanged historical Vosk report from older WAVs is rejected.
4. `stage/cues.json` is a v2 audio-bound, nonpublishing *candidate*. Run
   visual pixel verification and independent spoken-word / mathematical /
   figure / narrator-quality acceptance before any release.

The `capture`/ `align` CLI intentionally returns exit code **2** because
provisional ASR timing is not the project's release acceptance. Successful
offline candidate generation is signaled by a JSON report, not an exit-0
claim of publishability. Both CLI stages refuse overwrites.

## Verified evidence and limitations

- Parent is live PR #177 head
  `f1ed07453c7ef05edf04a02356a6e4e2cbbcd2b1`.
- Unit source replacement test: when slide 1 increases from 0.50 to 0.62 s,
  a later slide's global cue clock moves from 0.60 to 0.72 s; old report
  rejected even after legitimate WAV inventory and timeline updates.
- Other adversarial tests: malformed ASR confidence/clocks, missing/reordered
  slides, false publication evidence, old schema, existing cue-file collision,
  repeated observations, and a changed earlier WAV during ASR processing.
- Actual Dell-115 tests from this isolated checkout:
  `python -m pytest tests -q`: **738 passed, 3 skipped**.
  `python -m unittest discover -s tests -q`: **593 passed, 3 skipped**.
  Targeted audio/cue tests: **14 passed**.
- These use synthetic/review-fixture audio. The Dell-115 machine did **not**
  independently run the actual 17-slide corrected Thomas §2.5 Vosk pass
  here, so **0/17 corrected slides are newly audio-aligned by this PR**.
  Existing §2.5 video and original narration remain unchanged.
- Vosk transcriptions are automatically derived hypotheses. They cannot
  independently certify the correct pronunciation of `c.`, `y`, speaker
  identity, formula narration, mathematical graphics or final publishing.
- Local PC execution is **Dell-115 only** under the owner's existing original
  MicroGen_AI restriction. Earlier checkpoint descriptions of an HP campaign
  are historical, not permission to touch HP or Yoga 6 in this invocation.

## Next action

Construct a **new separate** 17-slide staged workspace from source-bound
historical corrected trial WAVs and original clips, never overwriting the
source; then acquire an installed offline Vosk model on Dell-115 only if
present under allowed local tools. Execute the two operations above on real
audio and inspect all replacement timestamps and their source PDF geometry.
If the local Vosk model or source-bound corrected audio is unavailable,
record the exact missing input and continue an independent semantic QA task.
No paid API, Whisper, new provider download, or publication is authorized.
