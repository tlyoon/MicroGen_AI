"""Exact source-PDF recovery for lateral-captioned vector graph panels.

A Docling picture extractor can miss an entirely vector-drawn graph.
Recover ONLY if a unique styled PDF caption lies directly to the right of
a row of 3-8 consecutive, fully labeled graph panels, each with independently
extractable axes/text and vector paths. The crop is a literal PDF render.
No OCR, Gemini guess, figure fabrication, publication, or permissive waiver.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pymupdf

from microgen_source_caption_vector_recovery import _styled_caption
from microgen_figure_composition import sha256

RECEIPT=".microgen_lateral_vector_figure_recovery.json"
CAPTION_LINE=re.compile(
    r"(?im)^\s*[-*]?\s*(?:\*\*)?Figure\s+(\d+\.\d+[a-z]?)\b")
SAFE_NAME=re.compile(r"Figure \d+\.\d+[a-z]?\.png\Z")


class LateralFigureError(ValueError):
    pass


def _all_spans(page):
    result=[]
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for item in line.get("spans", []):
                txt=item.get("text","").strip().lower()
                if txt:
                    result.append((txt, pymupdf.Rect(item["bbox"]), item))
    return result


def _lateral_geometry(page, label: str) -> dict:
    matches=_styled_caption(page,label)
    if len(matches)!=1:
        raise LateralFigureError("Missing or ambiguous uniquely styled source caption")
    caption=matches[0]["bbox"]
    width=page.rect.width
    if (caption.x0 < width*.66 or caption.width > width*.32
            or not page.rect.y0+60 < caption.y0 < page.rect.y1-65):
        raise LateralFigureError("Caption not isolated to the right of graph row")
    spans=_all_spans(page)
    # Source PDF often prints graph panel keys in small colored square
    # backgrounds. Require light, single-letter, consecutive panel labels.
    keys=[]
    for txt,rect,span in spans:
        color=int(span.get("color",0))
        red,green,blue=(color>>16)&255,(color>>8)&255,color&255
        if (len(txt)==1 and txt in "abcdefgh"
            and min(red,green,blue)>=220
            and rect.x0>page.rect.x0+width*.05
            and rect.x1<caption.x0-12
            and caption.y0+20<rect.y0<caption.y1+10
            and rect.width<20 and rect.height<17):
            keys.append((txt,rect))
    keys.sort(key=lambda item:item[1].x0)
    if not 3<=len(keys)<=8:
        raise LateralFigureError("Insufficient independently labeled graph panels")
    sequence="".join(item[0] for item in keys)
    if sequence!="abcdefgh"[:len(keys)]:
        raise LateralFigureError("Panel labels missing, reordered or ambiguous")
    ys=[r.y0 for _,r in keys]
    if max(ys)-min(ys)>7:
        raise LateralFigureError("Panel labels are not a single graph row")
    xs=[r.x0 for _,r in keys]
    gaps=[b-a for a,b in zip(xs,xs[1:])]
    if not all(25<=gap<=115 for gap in gaps):
        raise LateralFigureError("Panel labels lack independently spaced layout")
    drawings=[]
    for graphic in page.get_drawings():
        r=pymupdf.Rect(graphic.get("rect"))
        if (r.is_empty or r.width<17 or r.height<15 or r.get_area()<280
            or r.x0<page.rect.x0+width*.05
            or r.x1>=caption.x0-10
            or r.y0<caption.y0+5
            or r.y1>max(ys)-4):
            continue
        drawings.append(r)
    accepted=[];axis_boxes=[]
    for _,key in keys:
        center=(key.x0+key.x1)/2
        candidates=[r for r in drawings
                    if abs((r.x0+r.x1)/2-center)<27
                    and r.y1<key.y0-4 and r.y0>=caption.y0+5]
        if not candidates:
            raise LateralFigureError("Panel has no source-drawn graph axes")
        selected=max(candidates,key=lambda r:r.get_area())
        if not (20<=selected.width<=105 and 18<=selected.height<=95):
            raise LateralFigureError("Unsupported vector graph geometry")
        # Every graph needs both a time-axis symbol and a variable-axis
        # symbol, independently extractable from the actual source PDF.
        math_spans=[
            (txt,box) for txt,box,_ in spans
            if txt in {"t","v","a"}
            and box.x0>=selected.x0-14
            and box.x1<=selected.x1+17
            and box.y0>=selected.y0-18
            and box.y1<=key.y0-1
        ]
        if not (any(txt=="t" for txt,_ in math_spans) and
                any(txt in {"v","a"} for txt,_ in math_spans)):
            raise LateralFigureError("Source graph lacks labeled axes")
        accepted.append(selected)
        axis_boxes.extend(box for _,box in math_spans)
    all_boxes=accepted+[r for _,r in keys]+axis_boxes
    clip=pymupdf.Rect(
        min(r.x0 for r in all_boxes)-5,
        min(r.y0 for r in all_boxes)-5,
        max(r.x1 for r in all_boxes)+5,
        max(r.y1 for r in all_boxes)+5,
    )
    clip=clip & page.rect
    if (clip.width<width*.28 or clip.width>width*.72
        or clip.height<45 or clip.height>125
        or clip.x1>=caption.x0-8
        or clip.y0<caption.y0-17
        or clip.y1>caption.y1+13):
        raise LateralFigureError("Graph cannot be cropped without body/caption")
    return {
        "caption_bbox":[round(float(n),3) for n in caption],
        "crop_bbox":[round(float(n),3) for n in clip],
        "panel_labels":sequence,
        "vector_panels":len(accepted),
        "axis_label_spans":len(axis_boxes),
    }


def _identify(stage: Path, page_index: int, label: str) -> dict:
    if not re.fullmatch(r"\d+\.\d+[a-z]?",label):
        raise LateralFigureError("Unsafe source figure label")
    source=Path(stage)/"source.pdf"
    if not source.is_file() or source.is_symlink():
        raise LateralFigureError("Missing immutable source PDF")
    with pymupdf.open(source) as pdf:
        if not 0<=page_index<len(pdf):
            raise LateralFigureError("PDF page index outside source")
        geometry=_lateral_geometry(pdf[page_index],label)
    return {"source_page":page_index+1,
            "source_pdf_sha256":sha256(source),
            "figure_label":label,
            "destination":f"Figure {label}.png",
            **geometry}


def recover_lateral_figure(stage: Path, page_dir: Path, captions: str,
                           collector, *, only_labels: set[str] | None = None) -> list[str]:
    """Recover only otherwise unmapped, source-attested lateral graph(s).

    Called by the NORMAL caption mapping path after a Gemini figure batch
    fails to map any crop on a formally captioned textbook page.
    """
    stage=Path(stage)
    page_dir=Path(page_dir)
    if page_dir.parent.resolve()!= (stage/"pages").resolve():
        raise LateralFigureError("Unsafe page directory")
    m=re.fullmatch(r"page_(\d+)",page_dir.name)
    if not m:
        raise LateralFigureError("Unsafe figure page identity")
    index=int(m[1])-1
    labels=list(dict.fromkeys(CAPTION_LINE.findall(captions)))
    if only_labels is not None:
        if (not isinstance(only_labels,set)
                or not only_labels
                or not only_labels.issubset(set(labels))):
            raise LateralFigureError("Untrusted missing source-caption identities")
        labels=[label for label in labels if label in only_labels]
    if not 1<=len(labels)<=3:
        raise LateralFigureError("Missing or ambiguous formal figure captions")
    receipt_path=stage/RECEIPT
    prior={"schema_version":1,"status":"SOURCE_LATERAL_VECTOR_FIGURE_ATTESTED",
           "source_pdf_sha256":sha256(stage/"source.pdf"),
           "figures":[],"publication_allowed":False}
    if receipt_path.exists():
        prior=json.loads(receipt_path.read_text(encoding="utf8"))
        if (prior.get("schema_version")!=1
            or prior.get("status")!="SOURCE_LATERAL_VECTOR_FIGURE_ATTESTED"
            or prior.get("source_pdf_sha256")!=sha256(stage/"source.pdf")):
            raise LateralFigureError("Prior source-vector receipt is untrusted")
    planned=[]
    with pymupdf.open(stage/"source.pdf") as pdf:
        for label in labels:
            data=_identify(stage,index,label)
            if (not SAFE_NAME.fullmatch(data["destination"])
                or any(x["destination"]==data["destination"] for x in prior["figures"])):
                raise LateralFigureError("Duplicate or unsafe source-figure identity")
            rect=pymupdf.Rect(data["crop_bbox"])
            pix=pdf[index].get_pixmap(
                matrix=pymupdf.Matrix(2.0,2.0), clip=rect,alpha=False)
            if pix.width<180 or pix.height<80:
                raise LateralFigureError("Source vector render resolution too small")
            planned.append((data,pix.tobytes("png"),[pix.width,pix.height]))
    # Snapshot the source a second time before committing any recovered art.
    original_sha=sha256(stage/"source.pdf")
    if original_sha!=prior["source_pdf_sha256"]:
        raise LateralFigureError("Source PDF changed during vector render")
    created=[]
    try:
        for data,bytes_,pixels in planned:
            path=page_dir/("source_lateral_"+data["figure_label"].replace(".","_")+".png")
            with path.open("xb") as output:
                created.append(path)
                output.write(bytes_)
            data["source_crop_filename"]=path.name
            data["source_crop_sha256"]=sha256(path)
            data["pixel_size"]=pixels
            collector.add(stage/"pages"/data["destination"],path,
                          source_page=page_dir.name)
        prior["figures"].extend(row for row,_,_ in planned)
        temporary=receipt_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(prior,indent=2,sort_keys=True),encoding="utf8")
        temporary.replace(receipt_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return [data["destination"] for data,_,_ in planned]


def verify_lateral_figure_receipt(stage: Path) -> dict | None:
    """Repeat geometry and literal PDF crop SHA checks; no Gemini calls."""
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise LateralFigureError("Missing or unsafe source-vector proof")
    record=json.loads(path.read_text(encoding="utf8"))
    source=stage/"source.pdf"
    if (record.get("schema_version")!=1
        or record.get("status")!="SOURCE_LATERAL_VECTOR_FIGURE_ATTESTED"
        or record.get("publication_allowed") is not False
        or sha256(source)!=record.get("source_pdf_sha256")
        or not 1<=len(record.get("figures",[]))<=12):
        raise LateralFigureError("Invalid source-vector recovery source/receipt")
    from microgen_figure_composition import validate_figure_receipt
    # The normal mapper moves completed figure PNGs and their composition
    # receipt from pages/ to the stage root. Follow that existing validated
    # promotion, never assume a file remains at its pre-commit location.
    figure_root=(stage if (stage/"figure_composition_receipt.json").is_file()
                 else stage/"pages")
    composed=validate_figure_receipt(figure_root)
    by_dest={x["destination"]:x for x in composed["figures"]}
    with pymupdf.open(source) as pdf:
        for row in record["figures"]:
            page_index=row["source_page"]-1
            candidate=_identify(stage,page_index,row["figure_label"])
            if any(candidate[k]!=row[k] for k in candidate):
                raise LateralFigureError("Source vector geometry changed")
            directory=stage/"pages"/f"page_{page_index+1}"
            src=directory/row["source_crop_filename"]
            if (src.is_symlink() or row["pixel_size"][0]<180):
                raise LateralFigureError("Recovered source crop unsafe")
            # After private/source cleanup the original page crop may be gone.
            # Exact PDF re-render below is mandatory regardless. A retained
            # crop must additionally agree byte-for-byte if present.
            if src.exists() and sha256(src)!=row["source_crop_sha256"]:
                raise LateralFigureError("Recovered source crop changed")
            pix=pdf[page_index].get_pixmap(
                matrix=pymupdf.Matrix(2.0,2.0),
                clip=pymupdf.Rect(row["crop_bbox"]),alpha=False)
            if (hashlib.sha256(pix.tobytes("png")).hexdigest()!=row["source_crop_sha256"]
                or [pix.width,pix.height]!=row["pixel_size"]):
                raise LateralFigureError("Recovered figure not exact PDF render")
            composite=by_dest.get(row["destination"])
            if (not composite or composite["source_page"]!=f"page_{page_index+1}"
                or not any(x["sha256"]==row["source_crop_sha256"]
                           and x["filename"]==row["source_crop_filename"]
                           for x in composite["source_crops"])):
                raise LateralFigureError("Figure composition did not consume source recovery")
    return {"receipt_sha256":sha256(path),
            "figures":[r["destination"] for r in record["figures"]]}
