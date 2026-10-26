"""Diagnose missing generated figure assets against SOURCE textbook PDF graphics.

No hallucinated figures, no automatic pixel promotion to the slide mapping:
produce SHA-authenticated *candidate* source-region PNGs and fail closed.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
import pymupdf
from microgen_source_safe_orchestrator import atomic_json,digest


class SourceFigureRecoveryError(ValueError):
    pass


def missing_slide_figures(stage):
    s=Path(stage).resolve(strict=True)
    tex=s/"slides.tex"
    if not tex.is_file() or tex.is_symlink():
        raise SourceFigureRecoveryError("Beamer TeX required")
    names=re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}",
                     tex.read_text(encoding="utf8"))
    if not names:
        raise SourceFigureRecoveryError("No source figure references")
    result=[]
    for name in names:
        file=Path(name)
        if file.name!=name or ".." in file.parts or file.suffix.lower()!=".png":
            raise SourceFigureRecoveryError("Unsafe figure reference")
        if not (s/file).is_file():
            result.append(file.name)
    return sorted(set(result),key=str.casefold)


def _label(name):
    m=re.fullmatch(r"(?i:figure)[ ]+(\d+)\.(\d+)([a-zA-Z]?)\.png",name.strip())
    return (f"{int(m.group(1))}.{int(m.group(2))}"+m.group(3).lower()
            if m else None)


def _region(page,caption,*,scale=1.8):
    # Caption appears below a graph in typical textbook layout; use a broad
    # source-only candidate, never claim the ROI is the correct figure.
    pagebox=page.rect
    rectangle=pymupdf.Rect(
        max(pagebox.x0,caption.x0-18),
        max(pagebox.y0,caption.y0-135),
        min(pagebox.x1,caption.x0+230),
        min(pagebox.y1,caption.y1+14))
    drawing_score=0
    for d in page.get_drawings():
        q=d.get("rect")
        if q is None:continue
        inter=rectangle & q
        if not inter.is_empty and inter.get_area()>0:
            drawing_score+=min(inter.get_area(),800)
    return rectangle,round(drawing_score,2)


def propose_missing_figures(stage,output,*,pilot_recheck=None):
    s=Path(stage).resolve(strict=True)
    source=s/"source.pdf"
    if not source.is_file() or source.is_symlink():
        raise SourceFigureRecoveryError("Immutable source PDF required")
    absent=missing_slide_figures(s)
    if pilot_recheck is not None:
        # Explicit test-only simulation, not a production repair.
        if absent:
            raise SourceFigureRecoveryError("Cannot mix pilot simulation with real gaps")
        if not isinstance(pilot_recheck,str) or not (s/pilot_recheck).is_file():
            raise SourceFigureRecoveryError("Pilot must reference an existing source figure")
        absent=[pilot_recheck]
    if not absent or len(absent)>15:
        raise SourceFigureRecoveryError("Expected 1-15 actual missing figure references")
    out=Path(output).absolute()
    if (out.is_symlink() or out.exists() or out==s or out.is_relative_to(s)
            or s.is_relative_to(out)):
        raise SourceFigureRecoveryError("Unused isolated review folder required")
    pdf_hash=digest(source)
    proposals=[]
    with pymupdf.open(source) as pdf:
        if not 1<=len(pdf)<=1000:
            raise SourceFigureRecoveryError("Invalid original PDF page count")
        for name in absent:
            fid=_label(name)
            if fid is None:
                raise SourceFigureRecoveryError("Missing source graphic not named Figure X.Y.png")
            matches=[]
            for pgidx,page in enumerate(pdf):
                for caption in page.search_for("Figure "+fid):
                    r,score=_region(page,caption)
                    matches.append({"page":pgidx+1,
                                    "caption_bbox":[round(x,3) for x in caption],
                                    "crop_bbox":[round(x,3) for x in r],
                                    "drawing_score":score})
            if not matches:
                raise SourceFigureRecoveryError("Missing graphic has no matching source caption: "+fid)
            matches.sort(key=lambda m:m["drawing_score"],reverse=True)
            proposals.append({"requested_missing_name":name,"label":fid,
                              "candidate_regions":matches[:3],
                              "source_figure_verified":False,
                              "human_selection_required":True})
    out.mkdir(parents=True,exist_ok=False)
    try:
        images=[]
        with pymupdf.open(source) as pdf:
            for item in proposals:
                for idx,candidate in enumerate(item["candidate_regions"],1):
                    page=pdf[candidate["page"]-1]
                    rect=pymupdf.Rect(candidate["crop_bbox"])
                    file=f"Figure_{item['label']}_candidate_{idx:02d}_page_{candidate['page']:02d}.png"
                    path=out/file
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(1.8,1.8),
                                        clip=rect,alpha=False)
                    pix.save(path)
                    images.append({"name":file,"sha256":digest(path),
                                   "requested_name":item["requested_missing_name"],
                                   "score":candidate["drawing_score"]})
        if digest(source)!=pdf_hash:
            raise SourceFigureRecoveryError("Source changed while recovering")
        receipt={"status":"SOURCE_FIGURE_RECOVERY_CANDIDATES_UNVERIFIED",
                 "schema_version":1,"source_pdf_sha256":pdf_hash,
                 "requested_missing_figures":absent,
                 "pilot_simulation":pilot_recheck is not None,
                 "proposals":proposals,"images":images,
                 "figure_semantics_verified":False,
                 "source_crop_accepted":False,
                 "publication_allowed":False}
        atomic_json(out/"recovery_candidates_receipt.json",receipt)
        return {"requested":len(absent),"candidates":len(images),
                "pilot":pilot_recheck is not None,"publication_allowed":False}
    except Exception:
        shutil.rmtree(out)
        raise


def diagnose_before_graphics_gate(stage):
    """Invoked only for an actual missing TeX figure; never makes a fake repair."""
    s=Path(stage)
    try:
        missing=missing_slide_figures(s)
    except (OSError,SourceFigureRecoveryError):
        return None
    if not missing or not (s/"source.pdf").is_file():
        return None
    # New unique local review path. Existing artifact is never overwritten.
    prefix=s/".microgen_missing_source_figures_review"
    if prefix.exists():
        return str(prefix)
    try:
        return propose_missing_figures(s,prefix)
    except (OSError,ValueError,SourceFigureRecoveryError):
        return None


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--pilot-recheck")
    a=p.parse_args()
    print(propose_missing_figures(a.stage,a.output,
                                  pilot_recheck=a.pilot_recheck))


def check_graphics_with_source_candidates(tex_file):
    """Stop safely on missing imagery while preserving offline recovery evidence.

    Produces candidate crops for later source-grounded repair, NOT an image file
    silently inserted into the teaching deck.
    """
    from microgen_quality import check_graphics, QualityError
    path=Path(tex_file)
    try:
        return check_graphics(path)
    except (QualityError,FileNotFoundError):
        result=diagnose_before_graphics_gate(path.resolve().parent)
        if result:
            print("[source figures] candidate review saved before failed figure gate: "+
                  str(result),flush=True)
        raise
