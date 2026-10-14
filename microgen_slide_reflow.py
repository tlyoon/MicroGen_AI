"""Deterministic, math-preserving Beamer reflow for overloaded teaching frames.

No model calls. Only splits whole exampleblock or column environments, never a
math expression.  Every generated candidate is compiled in an isolated folder;
the original slides.tex and slides.pdf are unchanged until all checks pass.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from microgen_quality import (
    QualityError, check_graphics, check_slide_pdf, check_latex_overflow,
    normalize_latex_paragraphs, sha256,
)

FRAME_RX = re.compile(r"\\begin\{frame\}(?:\[[^\]\n]*\])?(?:\{[^{}\n]*\})?(.*?)\\end\{frame\}",re.S)
BLOCK_RX = re.compile(r"\\begin\{exampleblock\}\{[^{}\n]*\}.*?\\end\{exampleblock\}",re.S)
COLUMNS_RX = re.compile(r"\\begin\{columns\}(?:\[[^\]\n]*\])?(.*?)\\end\{columns\}",re.S)
COLUMN_RX = re.compile(r"\\begin\{column\}\{[^}\n]*\}(.*?)\\end\{column\}",re.S)
MATH_RX = re.compile(
    r"\\begin\{(align\*?|equation\*?|gather\*?|multline\*?|math|displaymath)\}.*?"
    r"\\end\{\1\}"
    r"|\\\[.*?\\\]"
    r"|(?<!\\)\$(?!\$).*?(?<!\\)\$",
    re.S,
)


def _math_evidence(tex: str) -> Counter[str]:
    return Counter(re.sub(r"\s+","",match.group()) for match in MATH_RX.finditer(tex))


def _split_frame(frame: str, mode: str) -> tuple[str, int] | None:
    m=FRAME_RX.fullmatch(frame)
    if not m:
        return None
    body=m.group(1)
    header=frame[:m.start(1)]
    if mode=="examples":
        groups=list(BLOCK_RX.finditer(body))
        if len(groups)<2:
            return None
        # Disallow a nested Beamer structure that a regexp could fracture.
        if re.search(r"\\begin\{(?:columns|column|frame|exampleblock)\}",body[:groups[0].start()]):
            return None
        output=[]
        start=0
        for index,g in enumerate(groups):
            section=body[start:g.end()]
            if index==0:
                section=body[:g.end()]
            output.append(header+section+r"\end{frame}")
            start=g.end()
        tail=body[start:]
        if tail:
            output[-1]=output[-1][:-len(r"\end{frame}")]+tail+r"\end{frame}"
        candidate="\n".join(output)
        return candidate,len(groups)
    if mode=="columns":
        all_columns=list(COLUMNS_RX.finditer(body))
        if len(all_columns)!=1:
            return None
        columns=all_columns[0]
        inside=columns.group(1)
        panels=list(COLUMN_RX.finditer(inside))
        if len(panels)<2:
            return None
        # Retain every non-column character once, without silently dropping
        # introductory text, equations, labels or post-column summaries.
        prefix=body[:columns.start()]
        suffix=body[columns.end():]
        rest=inside
        parts=[]
        for index,p in enumerate(panels):
            section=rest[:p.start()] if index==0 else inside[panels[index-1].end():p.start()]
            parts.append(section+p.group(1))
        trailing=inside[panels[-1].end():]
        if trailing.strip():
            parts[-1]+=trailing
        parts[0]=prefix+parts[0]
        parts[-1]+=suffix
        return "\n".join(header+item+r"\end{frame}" for item in parts),len(parts)
    raise ValueError(f"Unknown safe reflow mode {mode}")


def reflow_document(source: str, mode: str) -> list[tuple[str,str,int]]:
    matches=list(FRAME_RX.finditer(source))
    if not matches or len(matches)!=source.count(r"\begin{frame}") or len(matches)!=source.count(r"\end{frame}"):
        return []
    result=[]
    for m in matches:
        transformed=_split_frame(m.group(),mode)
        if transformed is None:
            continue
        replacement,count=transformed
        revised=source[:m.start()]+replacement+source[m.end():]
        if _math_evidence(revised)!=_math_evidence(source):
            continue
        result.append((revised,m.group(0)[:110],count))
    return result


def _set_total_if_provable(tex: str) -> str:
    """Only stamp totals for a plain, overlay-free Beamer deck."""
    count=len(list(FRAME_RX.finditer(tex)))
    if count<1 or count!=tex.count(r"\begin{frame}"):
        return tex
    # Frame counter totals are not equal to pages when any overlay or
    # hidden/againframe/appendix features are in use.
    hazards=(r"\pause",r"\only",r"\onslide",r"\againframe",
             r"\appendix",r"\framebreak",r"allowframebreaks",
             r"\noframenumbering")
    if any(token in tex for token in hazards) or r"\begin{frame}<" in tex:
        return tex
    return tex.replace(r"\inserttotalframenumber",str(count))


def _attempt_compile(tex: str, input_dir: Path, candidate_dir: Path,
                     *, timeout: float) -> tuple[bool,str,dict | None]:
    candidate_dir.mkdir(parents=True,exist_ok=True)
    path=candidate_dir/"slides.tex"
    path.write_text(tex,encoding="utf-8")
    # Copy only referenced visual assets and make sure missing graphics
    # cannot be skipped. Never use Google Drive as the scratch build path.
    try:
        images=re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}",tex)
        for name in images:
            src=(input_dir/name).resolve()
            if not src.is_file() or not src.is_relative_to(input_dir.resolve()):
                raise QualityError(f"Missing/unsafe referenced figure {name!r}")
            dest=candidate_dir/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dest)
        check_graphics(path)
    except (OSError,QualityError,ValueError) as exc:
        return False,f"figures: {exc}",None
    command=["pdflatex","-interaction=nonstopmode","-halt-on-error",
             "-file-line-error","slides.tex"]
    for i in (1,2):
        try:
            p=subprocess.run(command,cwd=candidate_dir,stdin=subprocess.DEVNULL,
                             capture_output=True,text=True,errors="replace",timeout=timeout)
        except (subprocess.TimeoutExpired,OSError) as exc:
            return False,f"pdflatex pass {i}: {exc}",None
        (candidate_dir/f"pdflatex_{i}.txt").write_text(
            p.stdout+"\n"+p.stderr,encoding="utf-8")
        if p.returncode:
            return False,f"pdflatex pass {i}: {p.stdout[-850:]}",None
    try:
        pdf=check_slide_pdf(candidate_dir/"slides.pdf",require_footer=True)
        overflow=check_latex_overflow(candidate_dir/"slides.log")
        return True,"accepted",{"pdf":pdf,"overflow":overflow}
    except (QualityError,OSError,ValueError) as exc:
        return False,f"slide quality: {exc}",None


def repair_layout(stage_tex: Path, *, timeout: float = 150,
                  max_candidates: int = 16) -> dict:
    """Try at most N deterministic candidates, commit only after validation.

    Requires a separately owned working directory. Retains a source-hash
    backup and transparent receipt. Returns status rather than silently
    modifying failed input.
    """
    stage_tex=Path(stage_tex)
    if not stage_tex.is_file() or stage_tex.name!="slides.tex":
        raise QualityError("Expected existing slides.tex file")
    stage=stage_tex.parent
    original=stage_tex.read_text(encoding="utf-8-sig")
    normalized=normalize_latex_paragraphs(original)
    before=_math_evidence(normalized)
    original_hash=sha256(stage_tex)
    scratch=stage/".microgen_structural_reflow"
    scratch.mkdir(exist_ok=True)
    queue=[("normalized",normalized,[])]
    inspected=set()
    results=[]
    while queue and len(inspected)<max_candidates:
        kind,tex,history=queue.pop(0)
        # Don't strip mathematical content in any way.
        if _math_evidence(tex)!=before:
            continue
        candidate=_set_total_if_provable(tex)
        fingerprint=hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        if fingerprint in inspected:
            continue
        inspected.add(fingerprint)
        num=len(inspected)
        location=scratch/f"candidate_{num:02d}"
        ok,reason,meta=_attempt_compile(candidate,stage,location,timeout=timeout)
        results.append({"candidate":num,"operations":history,
                        "passed":ok,"reason":reason[:950]})
        if ok:
            # Source hash guard protects against a background process writing
            # while an acceptance candidate was being compiled.
            if sha256(stage_tex)!=original_hash:
                raise QualityError("Source slides.tex changed during layout repair")
            backup=stage/f"slides.before_structural_reflow_{original_hash[:12]}.tex"
            if not backup.is_file():
                shutil.copy2(stage_tex,backup)
            proposed_pdf=location/"slides.pdf"
            proposed_tex=location/"slides.tex"
            for artifact in (proposed_tex,proposed_pdf):
                if not artifact.is_file() or not artifact.stat().st_size:
                    raise QualityError("Verified candidate missing final artifact")
            staged_pdf=stage/"slides.pdf.microgen-reflow.tmp"
            staged_tex=stage/"slides.tex.microgen-reflow.tmp"
            shutil.copy2(proposed_pdf,staged_pdf)
            shutil.copy2(proposed_tex,staged_tex)
            if sha256(staged_pdf)!=sha256(proposed_pdf) or sha256(staged_tex)!=sha256(proposed_tex):
                raise QualityError("Candidate staging hash mismatch")
            # Replace PDF and TEX only after both hashes are confirmed.
            staged_pdf.replace(stage/"slides.pdf")
            staged_tex.replace(stage_tex)
            shutil.copy2(location/"slides.log",stage/"slides.log")
            receipt={"schema_version":1,
                     "input_sha256":original_hash,
                     "output_tex_sha256":sha256(stage_tex),
                     "output_pdf_sha256":sha256(stage/"slides.pdf"),
                     "math_preserved":True,
                     "operations":history,
                     "original_frame_count":len(list(FRAME_RX.finditer(original))),
                     "result_frame_count":meta["pdf"]["pages"],
                     "attempts":results}
            tmp=stage/".microgen_structural_reflow_receipt.tmp"
            tmp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
            tmp.replace(stage/".microgen_structural_reflow_receipt.json")
            return {"status":"accepted",**receipt}
        # Evolve only from a *failed* trial. Put shorter, concept-level
        # example blocks ahead of side-by-side column splitting.
        for mode in ("examples","columns"):
            for revised,frame_label,count in reflow_document(tex,mode):
                if _math_evidence(revised)==before:
                    queue.append((mode,revised,history+[
                        {"mode":mode,"units":count,"original_frame":frame_label}]))
    return {"status":"not_repaired","attempts":results,"math_preserved":True}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--tex",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(repair_layout(args.tex),indent=2))
