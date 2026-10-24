"""Extract candidate displayed equations from *original* PDF line geometry.

Any math-looking line is a geometric hypothesis, not verified content
equivalence with the spoken narration or correct mathematical typesetting.
"""
from pathlib import Path
import re
import pymupdf as fitz
from microgen_source_safe_orchestrator import digest,atomic_json,OrchestratorError

class EquationGeometryError(OrchestratorError):
    pass

_MATH=re.compile(r"(?:=|→|≤|≥|≠|∫|∑|√|∞|\blim\b|\bsin\b|\bcos\b|\btan\b|\bIVT\b)")

def equation_region_inventory(pdf_file,output):
    pdf=Path(pdf_file).resolve(strict=True)
    target=Path(output).resolve(strict=False)
    if (pdf.is_symlink() or not pdf.is_file() or target.exists() or target.is_symlink()
        or target.is_relative_to(pdf.parent)):
        raise EquationGeometryError("Original PDF read-only; output must be separate")
    input_sha=digest(pdf)
    found=[]
    with fitz.open(pdf) as pages:
        if not 1<=pages.page_count<=2000:
            raise EquationGeometryError("Unbounded source PDF")
        for index,page in enumerate(pages,1):
            regions=[]
            for block in page.get_text("dict").get("blocks",[]):
                if block.get("type")!=0:continue
                for line in block.get("lines",[]):
                    spans=line.get("spans",[])
                    text="".join(s.get("text","") for s in spans).strip()
                    if not text or not _MATH.search(text) or len(text)>450:
                        continue
                    box=list(map(float,line["bbox"]))
                    if not page.rect.contains(fitz.Rect(box)):
                        raise EquationGeometryError("Outside PDF page geometry")
                    alpha=sum(c.isalpha() for c in text)
                    regions.append({"line_text":text,"bbox":box,
                      "geometry_kind":"MATH_EXPRESSION_CANDIDATE",
                      "mixed_prose_possible":alpha>35,
                      "semantic_content_verified":False})
            found.append({"slide":index,"regions":regions,
                "source_page_rect":[float(page.rect.width),float(page.rect.height)]})
    if digest(pdf)!=input_sha:raise EquationGeometryError("Original PDF changed midscan")
    report={"schema_version":1,"status":"PDF_MATH_LINE_GEOMETRY_CANDIDATES",
      "source_pdf_sha256":input_sha,"slide_count":len(found),
      "candidate_regions":sum(len(x["regions"]) for x in found),
      "slides":found,"math_correctness_verified":False,
      "spoken_equation_alignment_verified":False,"publication_allowed":False}
    atomic_json(target,report)
    return {"slides":len(found),"regions":report["candidate_regions"],
            "publication_allowed":False}
