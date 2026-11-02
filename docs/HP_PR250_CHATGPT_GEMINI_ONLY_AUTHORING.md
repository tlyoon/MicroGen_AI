# PR250 — permanent ChatGPT/Gemini-only private authoring

## Owner instruction

For the ORIGINAL MicroGen_AI project, the owner prohibits any local language models on the HP desktop or other machines. Do not install or use Ollama, Qwen, Llama or similar locally running inference software. Use ChatGPT or Gemini for original content generation; HP remains the only authorized development/testing machine for ordinary Python source extraction, QA, slides, WAV and video production. No unapproved paid APIs or external public uploads of textbook source.

This instruction supersedes the optional local model adapter introduced by historical PR248. PR250 REMOVES the obsolete microgen_private_local_authoring.py file and its tests from the active codebase.

## Model-free browser-content handoff

The new microgen_private_browser_authoring.py creates a fresh private prompt from section-bounded original PDF passages, including SHA-256 source identity and exact source passage IDs. It accepts independently authored ChatGPT/Gemini response as either one JSON object or a single fenced JSON object, with strict size and structure limits. It delegates rigorous source packet reconstruction, uncited numbers, long copied source spans, section boundaries, media term alignment, and transactional stage checks to PR247. The accepted standard private stage consists of source.pdf, narration.json, plan.json, contract.json, and authoring_private_qa.json, directly consumable by the existing slide/video pipeline.

This module has NO HTTP calls, no paid APIs, no local-model imports, no browser-profile manipulation, and no automatic network upload. The provider identity of a pasted browser response is not independently verifiable, but its source identity and text constraints are checked. An existing HP Chrome session without a debug port must not be closed, altered, or falsely described as connected to Gemini.

Command to prepare source text privately:

    python microgen_private_browser_authoring.py --source <private.pdf> --start-marker "Conversion of Units" --next-marker "Estimates and Order-of-Magnitude Calculations" --section-id 1.4 --new-private-prompt <new-private.txt>

Command to validate original ChatGPT/Gemini draft returned privately:

    python microgen_private_browser_authoring.py --source <private.pdf> --start-marker "Conversion of Units" --next-marker "Estimates and Order-of-Magnitude Calculations" --section-id 1.4 --browser-response <private-draft.json> --new-private-stage <fresh-private-directory>

Synthetic tests cover successful prompt creation and original JSON/fenced JSON imports, modified source, forged packet, malformed or extra response, and output overwrites. No external model is invoked in tests.

## Real new subsection

Serway Section 1.4, Conversion of Units, is a newly authored real section. The original read-only source is at G:\My Drive\Serway\Serway_1_7\1\1.4\source.pdf, kept only on HP. Discovery produces 13 bounded passages. ChatGPT in the current conversation created six original lecture topics: why conversions matter, length factors, unit cancellation, mile/kilometer distance reasoning, speed-limit comparison, and speedometer cross-check. Source contract and rendering passed: 6 slides, 10/13 passages anchored, 3 unmatched passages advisory. The private teaching slide PDF has SHA-256 7defa159cad636bb3602c6d6b3728c0fcdea34680808bc6e7c2c678d3e19fe90.

Source packet privately stored at %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_SERWAY14_NEW_PRIVATE_PACKET.json.
Private original drafted response stored at %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_SERWAY14_CHATGPT_AUTHORED_V2_PRIVATE_RESPONSE.json.
Private validated source/narration/plan/contract in %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_SERWAY14_NEW_CHATGPT_BROWSER_STAGE.
Private slides PDF in %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_SERWAY14_NEW_CHATGPT_SLIDES.

This is an UNPUBLISHED candidate, not proof of comprehensive scientific correctness, textbook rights, full figure mapping or formal narrator authorization. There are zero new copyrighted textbook excerpts/figures/narration/media in the GitHub repo.

## Next priorities

Source-claim semantic contradictions and coverage evidence beyond exact lexical anchors, safe mathematical symbol checks, broader multiple-section regression, rights and narration audit. No local models, no added manual academic reviewer gate, no brittle advisory ASR blocking. Keep full HP root pytest and four GitHub CI matrix jobs successful on the exact PR head before merge.

## Independently verified new original six-topic §1.4 private media

The ChatGPT-authored six-slide candidate completed the established offline candidate Piper WAV, advisory Vosk, and FFmpeg H.264/AAC video pipeline. A separate independent postflight rechecked the original PDF and contract SHA, six WAV hashes and PCM encoding, 6 decoded midpoint frames vs the source teaching slide PDF, and codecs/duration. Result: 6/6 slide frame comparisons passed with maximum normalized RGB error 0.005918; video duration 238.775 seconds; video SHA-256 4e33f0c47537a0e026e36e4cc45f88bd2c4af82b1a6575d5dd0253a1a37b196d; original source SHA-256 9dc28034e807304e242101d066790068477865f19d9a4bc04e5e474c2f7df3c5 unchanged; Vosk zero targeted pronunciation risk and zero advisory term misses. This is NOT evidence of comprehensive phonetic accuracy, academic completeness, textbook rights, or production voice approval. The video is PRIVATE under %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_SERWAY14_NEW_CHATGPT_OFFLINE_VIDEO\video\lecture_portable_neural_candidate.mp4; independent receipt under %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261102_HP_PR250_REAL_SERWAY14_INDEPENDENT_POSTFLIGHT.json.
