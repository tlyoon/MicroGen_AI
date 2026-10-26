# HP Milestone 1 — PR #198 two actual narrated highlighted candidate videos (26 October 2026)

This is original `tlyoon/MicroGen_AI`, exclusively **HP desktop** for local work, stacked on #197. No Dell-115, Yoga6, Zenbook, protected main, historical G: textbooks/MP4/WAV modifications, Whisper, paid speech models, Moodle/YouTube publication. A successful technical pilot is **not** final academic release.

## What changed

- `microgen_two_part_word_highlight.py`: independently source SHA validates the **current 23-slide PDF, all 23 fresh Chirp-3 WAVs and 146 high-confidence offline Vosk PDF word box candidates** from PR #197. Refuses forged publication flags or tampered PDF/WAV/word boxes/time windows. It renders every frame at source-cue time using actual PDF word boxes, instead of merely a static slide preview. The **13/10 split is enforced** and every encoded MP4 must be <600 seconds. Raw-video H264 includes the exact concatenated **mono 24kHz PCM, losslessly encoded as ALAC**. Writes in a new isolated HP AppData folder with per-video SHA, source PDF/audio and ASR report hashes, actual frame/cue counts and `publication_allowed=false`. No media copied to protected source tree. Results are word-level *candidate highlights*, not synchronized mathematical/figure semantics.
- `microgen_fresh_pixel_pcm_audit.py`: a **separate actual encoded-media verification pass** reads the two H264 MP4s, extracts sampled decoded frames and checks highlighted word regions show real visible changes against original PDF slide images; checks actual clean nonhighlight samples against original PDF to detect spurious overlays. Independently decodes the full audio from **both** videos and SHA-compares every PCM byte against concatenated current WAVs (not merely duration/codec tags). Refuses mismatched audio, tampered video sources and false publication. Produces a separately SHA-bound QA receipt with approval flags explicitly FALSE.

## Real HP artifacts and measured outcomes

- Source technical stage `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY\2.5` (new from the original Thomas Calculus PDF, 23 Beamer slides and 23 fresh WAVs). Slides.pdf SHA-256 `4f13819a17c100fd85b13348ec53d39b4012828c1aecc18d66885ba7a390b231`.
- Independent new Vosk recognition from #197: 23/23 audio clips, **146 source-PDF word cues**, fail closed on uncertain/repeated vocabulary.
- Real encoded outputs: `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_TWO_HIGHLIGHTED_PARTS_V1`, 7,285 frames and 750 active word-overlay frames, total 910.54s of source PCM.
  - Part 1: `part01_WORD_CUES_UNAPPROVED.mp4`, slides 1–13, **464.67 seconds = 7m44.67s**, SHA `d7e8ea0ca5a5ec92b3c91211c6aa3042343b67369f6ac99a6d4fd48f5d68d36c`.
  - Part 2: `part02_WORD_CUES_UNAPPROVED.mp4`, slides 14–23, **445.88 seconds = 7m25.88s**, SHA `87fa8e5de978db33bea1efdb80ba6c16a8058e251eac6627558b999662426972`.
- Independent second-pass output `C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_TWO_HIGHLIGHTED_INDEPENDENT_QA\independent_pixel_pcm_receipt.json`, SHA `5f3e15446b386e33b88e680e79c3ce15cc11760ed7b86295190f30dd1f1ce21a`: **23/23 selected positive source-word highlight locations visibly confirmed**, **4/4 negative clean-frame controls**, and **both video PCM SHA hashes exactly match** the original newly generated TTS samples. QA scripts make no assertion of correct phonemes, equations, speaker or figure highlights.
- Focused adversarial PR #198 tests **7 passed**; full HP regression and GitHub hosted CI to be verified separately.

## Remaining blocking acceptance evidence

- Correct mathematical and figure semantics *during spoken narration* not independently established. The **word cues only cover 146 conservatively matched unique words**, not every spoken word or figure; not a claim of continuous full-element synchronization.
- The existing TTS pronunciation risk scan flagged **69 possible risks on 16 slides**, none automatically a confirmed defect. Listening/c-y and single narrator approval, scientific figure review, 15 figure references (incl. one source-cropped Figure 2.38), and objective equation/figure-to-speech mapping remain unresolved.
- Publication, protected main merge and stable release are **not authorized solely by technical video reconstruction**. Next: targeted actual acoustic and source-semantic acceptance, then test 2–3 other textbook sections before package release. No more speculative PR counts.

Owner completion-first contract and HP-only hardware limitation take precedence over older Dell-only checkpoint entries.
