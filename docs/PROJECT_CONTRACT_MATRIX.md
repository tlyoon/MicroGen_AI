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

## Addendum — 25 Oct 2026 corrected lesson §2.5 (PRs #181–189; historical table above is stale)

The older matrix above describes original-sound candidate and HP-local earlier test segments. **Current owner amendment: Dell-115 ONLY for all original MicroGen_AI local coding, media testing and process checks. HP/Yoga6/Zenbook excluded.** The unmerged PR stack is not release.
| Contract criterion | Current status | Actual evidence and limitation |
|---|---|---|
| Exact 17 source slide PDF/script + unmodified protected assets | **PASS** | Source SHA-bound all stages, no edits to original G: media |
| Corrected lesson below 600s + actual full corrected audio | **PASS (technical)** | 552.75s H264/ALAC, decoded PCM exactly identical to full corrected WAV |
| Corrected slide-level PDF page timing | **PASS (sampled technical)** | 50/50 actual decoded PDF page pixel samples; limited guard interval |
| New corrected word overlays | **PASS (sampled technical)** | Fresh 17/17 Vosk ASR observations; 66 source SHA-bound PDF word cues, all 66 visible pixels and 64/64 available delayed non-highlight controls, 2 end-window controls not feasible |
| Offline speech/model recovery | **PASS (technical)** | Pinned source model ZIP SHA and per-slide model/WAV/PDF/source-bound resumable checkpoints; Vosk hypotheses only |
| Math spoken equation semantic correspondence | **PENDING** | 57 PDF math-looking candidates, only 1 contextual two-word hint, 57 decisions UNREVIEWED; heuristic not proof |
| Figure correctness and spoken figure linkage | **PENDING** | 34 geometry/crop candidates, all 34 decisions UNREVIEWED |
| Pronouncing c and y correctly | **PENDING** | Vosk output sees 'see/sea' or 'why'; not verified listening/phonetic correctness |
| Single narrator voice consistency | **PENDING** | Existing WAVs technically preserved; no independently verified voice identity |
| Independent academic/listening approval | **PENDING** | New offline reviewer packet, no completed approvals |
| Draft PR stack integration, publication | **BLOCKED** | Protected main unmodified; no upload to YouTube/Moodle |

### 25 Oct 2026 — current corrected acceptance gate v2
- Source, corrected 552.75s PCM video, 50/50 source slide samples, 66/66 active corrected word pixel samples, 64/64 feasible post-word controls, and all 130 reviewer files: **PASS, technical source-bound only**. See new `corrected_release_status_v2` report SHA `36f03062c3e71e48400c03c7d376b7ecd7a9eae87169a1fd04bc865c5c973c65` on Dell.
- Equation/audio correspondence: **PENDING 57/57**; figure/audio correspondence: **PENDING 34/34**. One contextual math ASR hint not independent semantics.
- Phonetic c/y listening, single narrator identity, full academic listening QA and release approval: **PENDING / BLOCKED**. No publication, no protected main merge. Historical old v1 release gate's missing-ASR and missing-pixel blockers are superseded, not proof of phonetic or scientific acceptance.

## 25 Oct 2026 exception-first reviewer queue — original MicroGen_AI §2.5
- Source SHA-pinned corrected acoustic/script/math/figure screening: **PASS as triage only**: 17 slides, 91 regions kept, 52 prioritized early, 39 deferred UNREVIEWED. Source pronunciation/voice/academic approval remain **BLOCKED**, and no source figure semantic claim follows from text overlap.
- Audio-format continuity: replacement slides 5/6/10 are mono 24k PCM16 vs 14 original mono 16k PCM16; not a defect by itself; screen for voice continuity separately. The full technical corrected MP4 PCM still passed #187–190.
- Release remains blocked; no Moodle/YouTube, protected main or G: source edits.

### 25 Oct 2026 — source-bound corrected PCM boundary screening
- 17 corrected §2.5 WAVs, 16 neighboring joins: **numerically screened**, 5 junctions flagged for exception QA including 9→10 potential no-fade seam (normalized amplitude jump 0.07312). This does not certify speaker, phonetic quality or actual audibility. All 16 joins remain UNREVIEWED for final listening and 91 mathematical/figure decisions remain unreviewed.
- Technical corrected source/media/PCM, 66 active cue pixels and 130 source-review file hashes still passed previously. No publication or protected main merge allowed solely from screening.
