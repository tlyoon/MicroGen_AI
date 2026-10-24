# MicroGen_AI — verified contract matrix (2026-10-24, Asia/Kuala_Lumpur)

**Project:** original `tlyoon/MicroGen_AI` (not MicroGen_AI_Web). Reference vertical slice: Thomas Calculus 13th edition, §2.5. This matrix is evidence-scoped to the exact historical §2.5 source and the unmerged draft stack.

| Criterion | State | Actual proof | Remaining obligation |
|---|---|---|---|
| Exact source PDF/narration lineage | PASS | 17 original PDF slides, source and script hashes verified by staged receipts; no originals changed | Recheck hashes before every new execution |
| Full historical decoded soundtrack | PASS (original only) | PR #163 sample-equal decoded PCM; original tail 1.023375 s preserved | Do not confuse with corrected trial |
| Sub-600-second lecture | PASS (original candidate) | 551.33 s ALAC and 551.25 s H.264/AAC, independent FFmpeg duration | Revalidate **corrected** candidate after generation |
| Word-level visible overlays | PASS 66/66 (original audio's selected words only) | Frame-before/during pixel checks on source-PDF bounding boxes, PR #164 | Not equivalent to full math/figure semantics |
| Avoid reusing old cue clock on changed WAV | FIX IN REVIEW (PR #177) | v2 cue manifest binds each WAV SHA, measured time, original PDF/script; negative tests reject v1 and replacement WAV | Hosted CI and merge verification; regenerate corrected cues |
| Mathematical equations in narration | PENDING | 57 PDF line candidates, only 1 conservative acoustic textual anchor | Independent context/semantic mapping and academic validation |
| Figures/graphs synchronized with narration | PENDING | 34 figure-crop pixel candidates, none near-blank in limited scan | Verify true figure panel, labels, transcript/audio alignment |
| Pronouncing letter c | FAIL/UNVERIFIED | Original slide 6 offline recognizer heard 'circa' 3 times; corrected historical WAV trial unapproved | Independently listen/verify corrected slide and phoneme |
| Pronouncing letter y | PENDING | Two corrected-trial 'why' ASR recognitions on slide 10 | Independent listening/phonetic QA |
| Single consistent speaker | PENDING | Provider voice-name claims; 6/16 shadow join loudness flags are **not** proof of different speaker | Authenticated voice and subjective QA |
| All-slide corrected lesson | FAIL/PENDING | Shadow corrected WAV 552.709 s staged; not synchronized into a corrected video | Re-recognize corrected audio and recompute all video cues |
| Offline, low-cost development | PASS this batch | HP local tests/FFmpeg/Vosk; no paid AI, Whisper or provider submission | No new paid services without explicit consent |
| Protected asset/main safety | PASS this batch | Isolated HP AppData clone, original G: teaching inputs and `main` untouched | Continue no overwrite, no cross-owner process interference |
| Review/production release | BLOCKED | Drafts through PR #176; no human academic/listening QA, no publish | No merge/publish until real acceptance, authorization and verification |

The original §2.5 technical MP4 is **not** an academically approved lecture. Passing a SHA, PCM, codec or pixel test never grants publication.
