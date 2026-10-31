# PR236 — Offline neural TTS qualification of 14-slide Serway 1.1

## Source inputs and test boundaries

The original MicroGen_AI is developed/tested only on authorized HP. PR235's 14-slide academic source/PDF/narration hashes and independent coverage report are prerequisites. The older 8-slide neural pilot is not accepted as complete input and is never overwritten.

`microgen_expanded_neural_tts.py` verifies the immutable textbook source PDF, Figure 1.1, actual 14-slide PDF and rendered receipt, independent academic coverage receipt, all 14 original narrator text hashes and source-topic join, and the local Piper model/model card/config. It generates 14 real mono PCM16 WAVs in a fresh private HP folder using no network or billed TTS. Per WAV, it verifies duration, RMS/non-silence, clipping and filesource identity. It never asserts formal voice acceptance or publication.

Spoken math conversions are deliberately narrow: explicit `\dot{C}` or `C-dot` may be expanded to `C dot`, and explicit `\dot{y}` to `y dot`. Ambiguous isolated prose letter abbreviations are rejected instead of guessing. Original input text is never modified; any synthesized replacement is separately SHA-bound.

`microgen_expanded_phonetic_advisory.py` reads a separately installed local Vosk model and the actual 14 WAVs. Its terminology observations accept common harmless spellings such as Planck/plank and cesium/caesium. The guard only *flags* ASR observations of circa where the original expression is explicitly C dot, or yay where explicitly y dot. Neither an ASR spelling mismatch nor a successful glossary match proves the phonetic quality of the whole audio.

## Real private HP evidence

- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR236_14_SLIDE_NEURAL_WAVS` holds slide01.wav through slide14.wav, all actually synthesized, totaling **899.379 seconds**, with `expanded_neural_qa_receipt.json`.
- `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR236_NEURAL_14_ASR_ADVISORY.json` holds optional offline Vosk observations and glossary/hazard counts once the actual pass completes.
- The unchanged source narration is `%LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR235_PRIVATE_EXPANDED_11_INPUT\expanded_narration_qa.json`.
- No source textbook PDF, figure, earlier WAV, MP4 or Google Drive asset was overwritten. No charged cloud-provider calls were made.

## Voice / academic / publication status

The Piper LJSpeech model card declares a **public-domain training dataset** and training from scratch, but this is not independently sufficient proof of the trained model weights' redistribution rights or suitability for public lecture distribution. No silent formal-voice selection occurs. The user's historical Google Cloud voice is an informational configuration, with Google Cloud allowed only for bounded diagnostic troubleshooting. The new local Piper voice remains a qualified *technical candidate*, not an automatically approved formal narrator. Original Cengage educational figures may also require permissions for external distribution.

PR236 does not produce an MP4, edit the academic lesson or claim that all words sound perfect. PR237 should assemble a **new 14-slide** source-to-MP4 candidate using these WAVs, independent slide-frame and phonetic checks, and enforce an explicit publication-release block until actual authorization/evidence exists.
## Evidence-driven correction trial

On the first complete neural pass, Vosk returned `meet her` when the source said `meter` (a plausible homophonic spelling) and `plane constant` where the source said `Planck constant`. A bounded private HP synthesis-only trial changed `Planck constant` to `Plank constant`; Vosk then returned `plank constant`. The source academic text and the rendered slide remain correctly spelled `Planck`. The narrowly scoped spoken lexicon now applies this correction only before the word `constant`, records the original and synthesis SHA separately, and regenerates a **new** private versioned 14-WAV candidate. The original 14 WAV candidates remain intact.

Both Vosk observations are fallible: improved ASR recognition is not independent acoustic proof. Formal voice selection, public redistribution permission, and scientific publication remain unapproved. Do not infer from this paired ASR trial that all other technical-term pronunciations are correct.