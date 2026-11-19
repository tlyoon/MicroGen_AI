"""Identify one mathematically material source-timed cue without ASR retry.

The two source-blind recognizers and original source/WAV SHA lineage
must have been independently captured before this pure selector runs.
An old rejected reviewer retake justifies targeted *new audio*, never
acceptance or rebilling the same WAV.
"""
from __future__ import annotations

import json
from pathlib import Path

MATERIAL_OPERATOR_FORMS={("divide","by"),("multiply","by")}


class SourceBoundCueSelectionError(RuntimeError):
    pass


def choose_material_operator_cues(stage:Path, report:dict,
                                  texts:list[str])->dict[int,list[int]]:
    """Return one-to-one timed cue selection, else fail closed (empty map)."""
    from microgen_tts_acoustic_qa import mismatch_details,tokens
    from microgen_timed_highlight_contract import (
        MANIFEST,inspect_timed_highlights,
    )
    stage=Path(stage)
    if not isinstance(report,dict) or not isinstance(texts,list):
        return {}
    flagged=report.get("review_required_slides",[])
    rows=report.get("slides",[])
    if (not isinstance(flagged,list) or len(flagged)!=1
            or not isinstance(rows,list) or len(rows)!=len(texts)
            or type(flagged[0]) is not int
            or not 1<=flagged[0]<=len(texts)):
        return {}
    n=flagged[0]
    row=rows[n-1]
    if (row.get("assessment")!="REVIEW_REQUIRED_PRONUNCIATION_RISK"
            or row.get("source_pronunciation_risks")
            or not isinstance(row.get("transcripts"),list)
            or len(row["transcripts"])!=2):
        return {}
    scores=[mismatch_details(texts[n-1],t) for t in row["transcripts"]]
    good=[i for i,v in enumerate(scores)
          if v["difference_fraction_upper_bound"]==0
          and v["sensitive_mismatches"]==0]
    if len(good)!=1:
        return {}
    bad=scores[1-good[0]]
    if (bad["difference_fraction_upper_bound"]>0.03
            or bad["sensitive_mismatches"]!=1
            or bad["circa_red_flags"] or bad["letter_y_yay_red_flags"]):
        return {}
    sensitive=[d for d in bad["differences"] if d["sensitive"]]
    if len(sensitive)!=1:
        return {}
    issue=sensitive[0]
    if issue["kind"]!="delete" or issue["recognized"]:
        return {}
    op=tuple(issue["expected"].split())
    if op not in MATERIAL_OPERATOR_FORMS:
        return {}
    # The disputed phrase must be a source-defined mathematical operator
    # appearing in exactly one cue; never infer from narration index alone.
    inspect_timed_highlights(stage)
    manifest=json.loads((stage/MANIFEST).read_text(encoding="utf8"))
    cue_list=manifest["slides"][n-1]["cues"]
    if len(cue_list)>12 or not cue_list:
        return {}
    candidates=[]
    for index,cue in enumerate(cue_list,1):
        if not isinstance(cue.get("spoken_text"),str):
            return {}
        t=tokens(cue["spoken_text"])
        if any(tuple(t[k:k+len(op)])==op for k in range(len(t)-len(op)+1)):
            candidates.append(index)
    if len(candidates)!=1:
        return {}
    return {n:candidates}
