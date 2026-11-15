"""Exact PDF-vector kinematics graph match evidence and private slide correction.

This rule does NOT assign graph meaning using model guesses. It recognizes
only an independently drawn six-panel v_x–t / a_x–t matching exercise,
measures the original PDF vector path topology, derives dv/dt and compares
shapes. Unknown panels abstain. The original PDF and previous campaign are
never changed. Corrections affect ONLY precompile Beamer text and require
independent science, acoustic, decoded-video and acceptance QA afterward.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pymupdf

from microgen_lateral_vector_figure_recovery import (
    _lateral_geometry, _styled_caption, _all_spans, LateralFigureError,
)
from microgen_figure_composition import sha256

RECEIPT=".microgen_source_kinematic_graph_audit.json"
CAPTION_RE=re.compile(r"(?i)\bFigure\s+(\d+\.\d+[a-z]?)\b")
PANEL_RE=re.compile(r"(?m)^[ \t]*\\item[ \t]+Graph[ \t]*\(([abc])\)[ \t]+[^\r\n]*")
STYLES={
    "a":"constant_positive_slope",
    "b":"increasing_positive_slope",
    "c":"positive_then_zero_slope",
    "d":"increasing_positive_acceleration",
    "e":"constant_positive_acceleration",
    "f":"positive_then_zero_acceleration",
}
# Source-derived dv/dt mapping, not a fixed name such as Figure 2.12.
DERIVATIVE_MATCH={
    "linear_positive":"flat_positive",
    "convex_positive":"linear_positive",
    "rise_then_flat":"step_positive_zero",
}
TEXT_BY_DERIVATIVE={
    "linear_positive":"has a constant positive slope, matching constant positive acceleration in graph",
    "convex_positive":"has an increasing positive slope, matching increasing acceleration in graph",
    "rise_then_flat":"rises and then levels off, matching positive then zero acceleration in graph",
}


class SourceGraphError(ValueError):
    pass


def _near(x,y,eps=1.8):
    return abs(x-y)<eps


def _stroke_kind(d, baseline):
    """Classify a single real colored vector path from visible PDF points."""
    strokes=d.get("items",[])
    if not strokes or d.get("type")!="s":
        raise SourceGraphError("Non-stroked vector graph unsupported")
    if any(z[0] not in ("l","c") for z in strokes):
        raise SourceGraphError("Unexpected plotted PDF vector primitive")
    if len(strokes)==1 and strokes[0][0]=="l":
        a,b=strokes[0][1:]
        dx=b.x-a.x;dy=b.y-a.y
        if dx>14 and dy< -10:
            return "linear_positive"
        if dx>14 and abs(dy)<2 and a.y<baseline-7:
            return "flat_positive"
    if len(strokes)==1 and strokes[0][0]=="c":
        a,c1,c2,b=strokes[0][1:]
        dx=b.x-a.x;dy=b.y-a.y
        if not (dx>14 and dy<-10 and c1.x>a.x and b.x>c2.x):
            raise SourceGraphError("Unrecognized PDF cubic graph")
        start=(a.y-c1.y)/(c1.x-a.x)
        end=(c2.y-b.y)/(b.x-c2.x)
        if 0<=start<end-0.3 and end>0.5:
            return "convex_positive"
    if len(strokes)==2 and all(z[0]=="l" for z in strokes):
        a,b=strokes[0][1:]
        c,d_=strokes[1][1:]
        if (a.x<b.x and c.x<d_ .x and _near(b.x,c.x)
                and _near(b.y,c.y) and b.y<a.y-8 and
                _near(d_.y,c.y) and _near(d_.y,b.y)):
            return "rise_then_flat"
    if len(strokes)==3 and all(z[0]=="l" for z in strokes):
        a,b=strokes[0][1:]
        c,e=strokes[1][1:]
        f,g=strokes[2][1:]
        if (b.x>a.x+6 and _near(a.y,b.y)
                and _near(b.x,c.x) and _near(b.y,c.y)
                and _near(c.x,e.x) and e.y>c.y+8
                and _near(e.x,f.x) and _near(e.y,f.y)
                and g.x>f.x+6 and _near(g.y,f.y)
                and _near(g.y,baseline)):
            return "step_positive_zero"
    raise SourceGraphError("Unrecognized source graph topology")


def _panels(page, figure_label):
    info=_lateral_geometry(page,figure_label)
    caption=pymupdf.Rect(info["caption_bbox"])
    spans=_all_spans(page)
    keys=[]
    for txt,rect,span in spans:
        color=int(span.get("color",0))
        red,green,blue=(color>>16)&255,(color>>8)&255,color&255
        if (len(txt)==1 and txt in "abcdef"
                and min(red,green,blue)>=220
                and caption.y0+20 < rect.y0 < caption.y1+10
                and rect.x1 < caption.x0-12):
            keys.append((txt,rect))
    keys.sort(key=lambda z:z[1].x0)
    if "".join(k for k,_ in keys)!="abcdef":
        raise SourceGraphError("Source panel labels not uniquely ordered")
    outcome={}
    for label,rect in keys:
        xcenter=(rect.x0+rect.x1)/2
        drawings=[]
        for d in page.get_drawings():
            box=pymupdf.Rect(d.get("rect"))
            color=d.get("color")
            if not color or len(color)<3:continue
            red,green,blue=color[:3]
            if (not (red>green+.18 and red>blue+.2)
                    or not d.get("width",0) or d["width"]<1.3
                    or d.get("type")!="s"
                    or box.y0<caption.y0+5
                    or box.y1>rect.y0-3
                    or abs((box.x0+box.x1)/2-xcenter)>24):
                continue
            drawings.append(d)
        if len(drawings)!=1:
            raise SourceGraphError(
                f"Expected one unique distinct plotted path for panel {label}")
        baseline=max(
            (pymupdf.Rect(x["rect"]).y1
             for x in page.get_drawings()
             if x.get("type")=="s"
             and x.get("color") and max(x["color"])<.3
             and abs((pymupdf.Rect(x["rect"]).x0+
                     pymupdf.Rect(x["rect"]).x1)/2-xcenter)<25
             and pymupdf.Rect(x["rect"]).width>=22
             and pymupdf.Rect(x["rect"]).height>=22
             and caption.y0+5<pymupdf.Rect(x["rect"]).y0
             <rect.y0-3),
            default=None)
        if baseline is None:
            raise SourceGraphError("No individually corroborated source axes")
        outcome[label]=_stroke_kind(drawings[0],baseline)
    if len(outcome)!=6 or len(set(outcome.values()))!=5:
        raise SourceGraphError("Unsupported graph topology count or duplication")
    # Each velocity graph must have exactly one derivative partner.
    mapping={}
    for v_label in "abc":
        expected=DERIVATIVE_MATCH.get(outcome[v_label])
        matches=[a for a in "def" if outcome[a]==expected]
        if len(matches)!=1:
            raise SourceGraphError("Cannot uniquely derive acceleration plot")
        mapping[v_label]=matches[0]
    if len(set(mapping.values()))!=3:
        raise SourceGraphError("Acceleration graph matching is not one-to-one")
    return {"figure_label":figure_label,"panel_shapes":outcome,
            "matching":mapping,
            "crop_bbox":info["crop_bbox"],
            "panel_label_count":6,
            "source_vector_attested":True}


def _source_match(stage:Path)->dict|None:
    source=stage/"source.pdf"
    if not source.is_file() or source.is_symlink():
        return None
    found=[]
    with pymupdf.open(source) as doc:
        for n,page in enumerate(doc,1):
            txt=page.get_text("text")
            if (not re.search(r"(?i)Quick\s+Quiz",txt)
                or not re.search(r"(?i)match\s+each",txt)
                or "graph" not in txt.lower()):
                continue
            for label in dict.fromkeys(CAPTION_RE.findall(txt)):
                if not _styled_caption(page,label):
                    continue
                try:
                    row=_panels(page,label)
                except (LateralFigureError,SourceGraphError):
                    continue
                row["source_page"]=n
                found.append(row)
    if not found:return None
    if len(found)!=1:
        raise SourceGraphError("Ambiguous source graph matching exercises")
    found[0]["source_pdf_sha256"]=sha256(source)
    return found[0]


def _proposed_tex(tex:str, source_row:dict)->tuple[str,list[dict]]:
    matches=list(PANEL_RE.finditer(tex))
    if not matches:return tex,[]
    letters=[m.group(1) for m in matches]
    if letters!=["a","b","c"]:
        # A labelled question may not be summarized at all, but where
        # generated text purports to answer, do not accept missing panels.
        raise SourceGraphError("Generated graph explanation omits or duplicates panels")
    replacements=[]
    edited=tex
    for m in reversed(matches):
        label=m.group(1)
        code=source_row["panel_shapes"][label]
        partner=source_row["matching"][label]
        suggested=(
            f"    \\item Graph ({label}) "
            f"{TEXT_BY_DERIVATIVE[code]} ({partner})."
        )
        old=m.group(0)
        # Source graph names must remain independent from injected TeX.
        if not old.strip().startswith(r"\item Graph"):
            raise SourceGraphError("Unsafe graph statement markup")
        edited=edited[:m.start()]+suggested+edited[m.end():]
        replacements.append({
            "panel":label,"was_sha256":hashlib.sha256(old.encode("utf8")).hexdigest(),
            "now_sha256":hashlib.sha256(suggested.encode("utf8")).hexdigest(),
            "derived_source_shape":code,"matched_to":partner,
        })
    return edited,list(reversed(replacements))


def auto_repair_source_graph_reasoning(stage:Path)->dict|None:
    """Run in normal slide generation before first LaTeX compile."""
    stage=Path(stage)
    receipt=stage/RECEIPT
    if receipt.exists() or receipt.is_symlink():
        # A retry must reverify the *same* source-derived mathematics;
        # never overwrite a previous repair or skip a failed proof.
        return verify_source_graph_repair(stage)
    proof=_source_match(stage)
    if proof is None:return None
    tex=stage/"slides.tex"
    if tex.is_symlink() or not tex.is_file():
        raise SourceGraphError("No genuine editable generated Beamer source")
    previous=tex.read_text(encoding="utf-8-sig")
    after,edits=_proposed_tex(previous,proof)
    if not edits:return None
    before_sha=hashlib.sha256(previous.encode("utf8")).hexdigest()
    if previous==after:
        return None
    receipt=stage/RECEIPT
    if receipt.exists() or receipt.is_symlink():
        raise SourceGraphError("Do not overwrite source-graph science proof")
    new_sha=hashlib.sha256(after.encode("utf8")).hexdigest()
    attestation={
        "schema_version":1,
        "status":"ORIGINAL_PDF_KINEMATIC_GRAPH_SEMANTICS_REPAIRED",
        "original_source_sha256":proof["source_pdf_sha256"],
        "source_figure":proof["figure_label"],
        "source_page":proof["source_page"],
        "source_vector_shapes":proof["panel_shapes"],
        "source_derivative_matching":proof["matching"],
        "original_generated_tex_sha256":before_sha,
        "repaired_tex_sha256":new_sha,
        "edits":edits,"independent_scientific_qa_required":True,
        "publication_allowed":False,
    }
    # The mapper, science QA and private acceptance MUST independently
    # revalidate this exact source-derived semantic repair receipt.
    tmp=tex.with_suffix(".tex.graph_tmp")
    tmp.write_text(after,encoding="utf8")
    tmp.replace(tex)
    receipt.write_text(json.dumps(attestation,indent=2,sort_keys=True),
                       encoding="utf8")
    verified=verify_source_graph_repair(stage)
    if verified is None:
        raise SourceGraphError("Repaired graphical reasoning did not reverify")
    print("[source graph] recovered exact source vector-derived "
          f"kinematic matching {proof['matching']}; original and source "
          "mathematics left intact",flush=True)
    return verified


def verify_source_graph_repair(stage:Path)->dict|None:
    stage=Path(stage)
    recfile=stage/RECEIPT
    if not recfile.exists():return None
    if recfile.is_symlink() or not recfile.is_file():
        raise SourceGraphError("Unsafe source graph receipt")
    record=json.loads(recfile.read_text(encoding="utf8"))
    source=_source_match(stage)
    if (not source or record.get("schema_version")!=1
        or record.get("status")!="ORIGINAL_PDF_KINEMATIC_GRAPH_SEMANTICS_REPAIRED"
        or record.get("publication_allowed") is not False
        or record.get("independent_scientific_qa_required") is not True
        or record.get("original_source_sha256")!=source["source_pdf_sha256"]
        or record.get("source_figure")!=source["figure_label"]
        or record.get("source_page")!=source["source_page"]
        or record.get("source_vector_shapes")!=source["panel_shapes"]
        or record.get("source_derivative_matching")!=source["matching"]):
        raise SourceGraphError("Original graph semantics attestation changed")
    tex=(stage/"slides.tex")
    if (tex.is_symlink() or not tex.is_file() or
        hashlib.sha256(tex.read_text(encoding="utf-8-sig").encode("utf8")).hexdigest()
        !=record.get("repaired_tex_sha256")):
        raise SourceGraphError("Source-based Beamer graph correction changed")
    # The original complete text cannot be reconstructed after normal
    # generation cleanup, but every final panel sentence must still exactly
    # reflect independently extracted source vector physics.
    final=tex.read_text(encoding="utf-8-sig")
    statements=list(PANEL_RE.finditer(final))
    if len(statements)!=3 or [m.group(1) for m in statements]!=["a","b","c"]:
        raise SourceGraphError("Repaired graph panel count changed")
    for match in statements:
        label=match.group(1)
        expected=f"    \\item Graph ({label}) {TEXT_BY_DERIVATIVE[source['panel_shapes'][label]]} ({source['matching'][label]})."
        if match.group(0)!=expected:
            raise SourceGraphError("Repaired physics text no longer source-grounded")
    return {
        "status":record["status"],"figure":record["source_figure"],
        "matching":record["source_derivative_matching"],
        "receipt_sha256":sha256(recfile),
    }

def require_graph_source_evidence(stage: Path) -> dict | None:
    """Fail closed on an unbound graphical solution to a source-vector quiz."""
    stage=Path(stage)
    tex=stage/"slides.tex"
    if not tex.is_file() or tex.is_symlink():
        return None
    prose=tex.read_text(encoding="utf-8-sig")
    if not PANEL_RE.search(prose):
        if (stage/RECEIPT).exists():
            raise SourceGraphError("Source graph receipt without graph statements")
        return None
    proof=_source_match(stage)
    if proof is None:
        # This module does not claim to cover another textbook graph layout.
        if (stage/RECEIPT).exists():
            raise SourceGraphError("Source graph receipt cannot be reconfirmed")
        return None
    result=verify_source_graph_repair(stage)
    if result is None:
        raise SourceGraphError(
            "SOURCE_GRAPH_REASONING_UNVERIFIED: graph matching solution "
            "must be checked against original PDF vector derivatives"
        )
    return result
