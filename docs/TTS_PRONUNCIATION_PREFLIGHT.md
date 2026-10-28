# TTS mathematical-pronunciation preflight (PR #23)

The TTS layer distinguishes source narration from the audio-only normalization.
Original `script.txt`, `script_tts.json`, PDFs, and slides are never rewritten
by this preflight. It supports a bounded set of deterministic Unicode mathematical
symbol names, building on the sentence-final mathematical `c.` fix in PR #22.

## Offline check before spending TTS resources

```powershell
python microgen_pronunciation.py "path\to\script_tts.json"
```

Exit 0 indicates *no covered ambiguity found*, **not** a guarantee of correct
pronunciation. Exit 2 indicates review-required items and prints slide identifiers,
short local excerpts and issue codes. The synthesis pipeline also checks every
slide before producing any WAV and applies the same check to direct synthesis.

Blocking examples: unexpanded mathematical `c.` after math cues, raw LaTeX commands
such as `\sqrt`, and spoken input containing raw variable subscripts like
`x_1`. The transformation deliberately does not guess the correct spoken
equation for these structures; the narration author must supply reviewed TTS text.
Dates such as `c. 1900`, `C. Smith`, and ordinary `Appendix C.` remain unchanged.

## Boundaries

This is an **offline textual preflight**, not an audio recognizer or acoustic
pronunciation proof. No Whisper/ASR dependency is installed. It cannot detect
every abbreviation, semantic mismatch, language ambiguity, or audio-engine
misreading. Listening and mathematical review remain separate release gates.

Existing TTS provider and fallback selection, original assets, 600-second video
contract, and figure/highlighting QA contracts are not altered.
