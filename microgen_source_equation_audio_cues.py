"""Source-bound, narrowly recognized equation-element audio cue candidates.

Only explicitly enumerated math phrases, unique original PDF equation lines,
and high-confidence observed current WAV anchors can emit candidates.
No provider/API/Whisper calls, no academic or phonetic approval.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from pathlib import Path

import pymupdf as fitz

from microgen_source_safe_orchestrator import atomic_json, digest, read_json
from microgen_fresh_source_cues import source_inventory
from microgen_two_part_word_highlight import validate


class EquationAnchorError(ValueError):
    pass


RULES = (
    {
        "id": "CUBIC_IVT_EXAMPLE",
        "narration_phrase": "x cubed minus x minus 1",
        "pdf_pattern": r"f\s*\(x\)\s*=\s*x3\s*-\s*x\s*-\s*1",
        "word": "cubed",
        "preceding": "equals",
        "preceding_max_gap": 2.5,
        "following": None,
        "following_max_gap": 0,
    },
    {
        "id": "SQUARE_ROOT_IVT_EQUATION",
        "narration_phrase": "square root of the quantity 2x plus 5 equals 4 minus x squared",
        "pdf_pattern": r"√\s*2x\s*\+\s*5\s*=\s*4\s*-\s*x2",
        "word": "root",
        "preceding": "square",
        "preceding_max_gap": 1.0,
        "following": "equals",
        "following_max_gap": 4.0,
    },
)


def normalize_line(s):
    return re.sub(r"\s+", " ", s.replace("−", "-").replace("–", "-")).strip()


def source_equation_lines(page):
    """Original PDF text line bbox, not a guessed equation from narration."""
    result=[]
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            content="".join(span.get("text","") for span in line.get("spans",[]))
            if not content.strip():
                continue
            box=fitz.Rect(line["bbox"])
            if box.is_empty or not page.rect.contains(box):
                # Ignore unrelated clipped PDF lines; never emit invalid boxes.
                continue
            result.append({"text":normalize_line(content),
                           "box":[float(x) for x in box]})
    return result


def equation_candidates(narration, lines, words, *, duration):
    """Return only unambiguous equation lines with bounded observed word times."""
    if (not isinstance(narration,str) or not isinstance(lines,list) or
            not isinstance(words,list) or not isinstance(duration,(int,float)) or
            not math.isfinite(duration) or duration<=0):
        raise EquationAnchorError("Invalid original narration/geometry/clock")
    observed=[]
    for word in words:
        if not isinstance(word,dict):
            raise EquationAnchorError("Malformed recognized word")
        start,end,conf=(word.get("start"),word.get("end"),word.get("conf"))
        if (not all(isinstance(x,(float,int)) and not isinstance(x,bool)
                    and math.isfinite(x) for x in (start,end,conf)) or
                not 0<=start<end<=duration+.02 or not 0<=conf<=1):
            raise EquationAnchorError("Out-of-bounds recognized word evidence")
        observed.append((re.sub(r"[^a-z]","",str(word.get("word","")).lower()),
                         float(start),float(end),float(conf)))
    result=[]
    for rule in RULES:
        if rule["narration_phrase"] not in narration.lower():
            continue
        hits=[line for line in lines
              if re.search(rule["pdf_pattern"],normalize_line(line["text"]))]
        if len(hits)!=1:
            continue
        valid=[]
        for i,(token,start,end,conf) in enumerate(observed):
            if token!=rule["word"] or conf<.9:
                continue
            prev=rule["preceding"]
            next_=rule["following"]
            preceding_ok=(not prev or any(
                x[0]==prev and x[3]>=.9 and 0<=start-x[2]<=rule["preceding_max_gap"]
                for x in observed[:i]))
            following_ok=(not next_ or any(
                x[0]==next_ and x[3]>=.9 and 0<=x[1]-end<=rule["following_max_gap"]
                for x in observed[i+1:]))
            if preceding_ok and following_ok:
                valid.append((start,end,conf))
        if len(valid)!=1:
            continue
        start,end,conf=valid[0]
        region=hits[0]
        result.append({"text":"UNVERIFIED_MATH_ELEMENT_"+rule["id"],
            "start":round(max(0.,start-.18),3),
            "end":round(min(duration,end+.7),3),
            "confidence":round(conf,4),
            "box":region["box"],"cue_kind":"SPOKEN_FORMULA_TOKEN_PDF_LINE",
            "matched_source_formula_line":region["text"],
            "matched_narration_phrase":rule["narration_phrase"],
            "mathematical_equivalence_verified":False,
            "equation_phrase_fully_synchronized":False})
    return result


def create_equation_cues(stage, prior_cues, asr_dir, new_dir):
    base,source,original=validate(stage,prior_cues)
    output=Path(new_dir).resolve(strict=False)
    audio=Path(asr_dir).resolve(strict=True)
    prior_file=Path(prior_cues).resolve(strict=True)
    if (output.exists() or output.is_symlink() or output==base or
            output.is_relative_to(base) or base.is_relative_to(output) or
            output.is_relative_to(audio) or output.is_relative_to(prior_file.parent)
            or not audio.is_dir() or audio.is_symlink()):
        raise EquationAnchorError("New independent QA directory and original ASR needed")
    slide_hash=digest(base/"slides.pdf")
    script_hash=digest(base/"script_tts.json")
    prior_hash=digest(prior_file)
    script=read_json(base/"script_tts.json").get("slides")
    if not isinstance(script,list) or len(script)!=source["slide_count"]:
        raise EquationAnchorError("Original narration inventory changed")
    augmented=json.loads(json.dumps(original))
    qa_rows=[]
    asr_hashes={}
    with fitz.open(base/"slides.pdf") as pdf:
        for idx,page in enumerate(pdf,1):
            asr_file=audio/f"slide{idx:02d}.json"
            if not asr_file.is_file() or asr_file.is_symlink():
                raise EquationAnchorError("Unrecognized slide; no inferred timing")
            report=read_json(asr_file)
            expected=source["wav_inventory"][idx-1]["wav_sha256"]
            rec=report.get("recognition")
            if (report.get("slide")!=idx or report.get("wav_sha256")!=expected
                    or report.get("publication_allowed") is not False or
                    not isinstance(rec,dict) or
                    rec.get("source_wav_sha256")!=expected or
                    rec.get("phonetic_identity_verified") is not False or
                    rec.get("semantic_word_alignment_certified") is not False):
                raise EquationAnchorError("Untrusted actual WAV/ASR source binding")
            cues=equation_candidates(
                script[idx-1]["tts_text"],source_equation_lines(page),
                rec.get("words"),duration=source["wav_inventory"][idx-1]["duration_seconds"])
            augmented["slides"][idx-1]["cues"].extend(cues)
            augmented["slides"][idx-1]["cues"].sort(key=lambda q:q["start"])
            if cues:
                qa_rows.append({"slide":idx,"cues":cues,
                    "wav_sha256":expected,"observed_asr_sha256":digest(asr_file),
                    "mathematical_correctness_verified":False})
            asr_hashes[asr_file.name]=digest(asr_file)
    augmented["total_cues"]=sum(len(x["cues"]) for x in augmented["slides"])
    if (digest(base/"slides.pdf")!=slide_hash or
            digest(base/"script_tts.json")!=script_hash or
            digest(prior_file)!=prior_hash or source_inventory(base)[1]!=source or
            any(digest(audio/name)!=sha for name,sha in asr_hashes.items())):
        raise EquationAnchorError("Actual source or WAV recognition changed")
    output.mkdir(parents=True,exist_ok=False)
    try:
        file=output/"equation_augmented_cues.json"
        atomic_json(file,augmented)
        validate(base,file)
        receipt={"status":"SOURCE_PDF_EQUATION_TOKEN_TIME_CANDIDATES_NOT_PROOF",
            "schema_version":1,"source":source,
            "base_cue_sha256":prior_hash,"augmented_cue_sha256":digest(file),
            "slide_pdf_sha256":slide_hash,"script_sha256":script_hash,
            "asr_sha256":asr_hashes,"candidate_slides":qa_rows,
            "equation_candidate_count":sum(len(row["cues"]) for row in qa_rows),
            "mathematics_verified":False,"full_element_sync_verified":False,
            "phonetic_correctness_verified":False,"publication_allowed":False}
        atomic_json(output/"equation_audio_cue_receipt.json",receipt)
        return receipt
    except Exception:
        shutil.rmtree(output)
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for name in ("stage","prior_cues","asr_dir","new_dir"):
        parser.add_argument("--"+name.replace("_","-"),required=True)
    args=parser.parse_args()
    r=create_equation_cues(args.stage,args.prior_cues,args.asr_dir,args.new_dir)
    print(json.dumps({"equation_candidate_count":r["equation_candidate_count"],
                      "slides":[x["slide"] for x in r["candidate_slides"]],
                      "publication_allowed":False}))
