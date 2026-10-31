# PR235 — Source-bounded academic coverage of Serway 1.1

The original four-page PDF includes the start of section 1.2 on its last page. The independent section audit truncates at that boundary before checking the fourteen section-1.1 source anchors and topic groups.

The former eight-slide lecture is preserved unchanged. The new candidate uses fourteen source-aligned slides and fourteen 140–180-word narration passages; six new passages expand previously undercovered history, measurement scales, mass versus weight, customary units, prefixes and derived dimensions. Its narration text, plan, source and figures remain on authorized HP only, not in the public code repository.

The new source checker validates the original PDF and image hashes, fourteen concept/topic/source-page joins, narration text SHA and word count, visible slide coverage, source-supported numeric facts, the correct 2019 Planck-based kilogram correction with official link, the density quiz, exact original figure pixel identity, and the exclusion of section 1.2. The renderer supports both original 8-slide and expanded 14-slide modes. For 14-slide rendering, invoke render_teaching_candidate with figure_slide=7 and historical_si_slide=6.

Private real HP results:
- %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR235_PRIVATE_EXPANDED_11_INPUT\expanded_narration_qa.json
- %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR235_PRIVATE_EXPANDED_11_INPUT\expanded_visual_plan.json
- %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR235_EXPANDED_SECTION11_DECK\slides_teaching_candidate.pdf
- %LOCALAPPDATA%\MicroGen_AI_Checkpoints\20261031_HP_PR235_RENDERED_SECTION_COVERAGE_REPORT.json

Use microgen_section_academic_coverage.py arguments --source-stage, --narration-qa, --visual-plan, --rendered-dir and --new-report to independently re-audit fresh output. Source-specific narration and plan files are deliberately private.

The output remains a NOT-FOR-PUBLICATION academic candidate. The deterministic 14-topic coverage check is evidence that the enumerated teaching concepts appear, not proof of every academic sentence or independent phonetic correctness. Neither production TTS nor a new MP4 is within PR235. No cloud provider fees, source mutation, manual academic sign-off prerequisites or automatic publication.