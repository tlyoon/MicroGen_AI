# MicroGen_AI: independent TTS acoustic QA protocol

## Why
Thomas Calculus 2.5 demonstrated that script validity, a checksum and a single configured TTS voice do not prove pronunciation correctness: mathematical `c.` may be read as *circa*. The separate complaint at approximately 4:54 in the same lecture requires examination of the **actual audio**, not another blind script replacement.

## Seven QA stages
1. Write a separate, precise `tts_text` for each slide, backed by a reviewed mathematical pronunciation lexicon covering variables, math names, theorem names, numbers, operators, acronyms and units. Keep the mathematical slide/narration intact.
2. Run deterministic text preflight (PR #23), fail on raw LaTeX and ambiguous math notation. Do not confuse dates such as `c. 1900` with mathematical c.
3. Generate one provider- and voice-locked set of WAVs with checksums and technical provenance (PR #24). A mixed or unpinned voice is not certified.
4. **Independently transcribe every slide WAV twice** using two distinct configured audio models without providing the expected text. Compare word sequences to the normalized TTS input with a strict maximum 5% discrepancy, and flag changed/missing/extra mathematical terms, unrecognized audio, and the known circa/C defect.
5. Produce a slide-specific list of exceptions and checksums. Correct TTS-specific text only; regenerate safely with the same pinned voice; re-audit affected and dependent output.
6. Require a lecturer's listening approval, especially for all flagged scientific passages. Two recognizers can agree on the *same* incorrect transcription and cannot guarantee phonetic accuracy. Academic, figure and element-level highlight QA remain separate.
7. **Fail closed** when model inference is unavailable, quota is exhausted, an input has changed, the WAV is corrupted, the two recognizers disagree, or independent listening has not been approved. Never label these outputs publishable.

## Running the acoustic screen
Run after PR #24 has written `.microgen_tts_provenance.json` into an isolated, writable lecture copy:

```powershell
python microgen_tts_acoustic_qa.py "C:\safe\staging\section2.5" --primary-model gemini-3.5-flash --secondary-model gemini-3.8-flash
```

The tool reads `script_tts.json` and numbered `slideN.wav` files, verifies original audio provenance, and writes `.microgen_tts_acoustic_qa.json` without overwriting any previous report. API credentials stay in the user's local Microvid configuration. Live recognition may incur usage costs; **no Whisper installation** is required. Exit zero indicates only that no issue was found by these recognizers, not publication approval.

## Limitations and deployment
Recognition may silently repair mispronunciations, normalize homophones or miss stress/prosody. Two related models provide only partial independence. This PR introduces a fail-closed **acoustic-screen stage and API**, not an automatic replacement for expert listening or an end-to-end integration with all existing legacy release paths. The publication gate must be wired into the corresponding production pipeline before this can be claimed to protect every lecture.

For the uploaded 2.5 video, speech analysis around 4:54 could not be completed because the configured services returned 503 unavailable / quota limitations. That is a **review-required** outcome, not a pass.
