"""Compare original two-panel textbook figure pixels to candidate PDF embedding.

Caption/label corroboration is textual; pixels alone cannot identify objects.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_source_slide_draft import normal

class FigurePanelError(ValueError):pass

def inspect_serway_figure(stage:Path,slides:Path,narration:Path,claims:Path)->dict:
    stage,slides,narration,claims=map(Path,(stage,slides,narration,claims))
    paths={"source":stage/"source.pdf","figure":stage/"Figure 1.1.png",
        "slides":slides/"slides_teaching_candidate.pdf",
        "manifest":slides/"teaching_slide_receipt.json",
        "narration":narration,"claims":claims}
    if any(p.is_symlink() or not p.is_file() for p in paths.values()):
        raise FigurePanelError("Original textbook source and fresh independent receipts required")
    hashes={key:sha(path) for key,path in paths.items()}
    m=json.loads(paths["manifest"].read_text(encoding="utf8"))
    n=json.loads(narration.read_text(encoding="utf8"))
    c=json.loads(claims.read_text(encoding="utf8"))
    if (m.get("status")!="FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
        or m.get("source_pdf_sha256")!=hashes["source"]
        or m.get("figure_sha256")!=hashes["figure"]
        or m.get("rendered_pdf_sha256")!=hashes["slides"]
        or m.get("narration_qa_sha256")!=hashes["narration"]
        or m.get("slide_count")!=8
        or m.get("figure_slide")!=5
        or m.get("publication_allowed") is not False
        or n.get("publication_allowed") is not False
        or c.get("publication_allowed") is not False
        or c.get("status")!="EIGHT_CRITICAL_SOURCE_CLAIM_GROUPS_SPOT_CHECKED"
        or c.get("source_pdf_sha256")!=hashes["source"]
        or c.get("narration_qa_sha256")!=hashes["narration"]
        or c.get("teaching_slides_sha256")!=hashes["slides"]):
        raise FigurePanelError("Untrusted figure provenance or false publication status")
    with fitz.open(paths["source"]) as original, fitz.open(paths["slides"]) as rendered:
        if len(original)!=4 or len(rendered)!=8:raise FigurePanelError("Source page/slide count changed")
        caption=normal(original[1].get_text())
        for required in ("figure11","internationalprototypeofthekilogram",
                         "acesiumfountainatomicclock"):
            if required not in caption:
                raise FigurePanelError("Original figure/caption identities absent")
        visible=normal(rendered[4].get_text())
        for required in ("panela","historicalkilogramprototype",
                         "panelb","cesiumfountainatomicclock"):
            if required not in visible:
                raise FigurePanelError("Figure panel names do not agree with source caption")
        speech=n["slides"][4]["narration"].lower()
        for word in ("left panel","right panel","mass","clock"):
            if word not in speech:
                raise FigurePanelError("Narration-to-caption panel alignment incomplete")
        page=rendered[4]
        embedded=page.get_images(full=True)
        if len(embedded)!=1:raise FigurePanelError("Exactly one original figure composite required")
        xref=embedded[0][0]
        rects=page.get_image_rects(xref)
        if len(rects)!=1 or not page.rect.contains(rects[0]):
            raise FigurePanelError("Composite figure is clipped/missing in teaching PDF")
        pix=fitz.Pixmap(rendered,xref)
        if pix.n not in (3,4):raise FigurePanelError("Unsupported original figure color components")
        if pix.n!=3:
            pix=fitz.Pixmap(fitz.csRGB,pix)
        embedded_img=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
        with Image.open(paths["figure"]) as original_img:
            original_rgb=original_img.convert("RGB")
        if embedded_img.size!=original_rgb.size:
            raise FigurePanelError("Embedded figure was downsampled or replaced")
        width,height=original_rgb.size
        if width<40 or height<40:raise FigurePanelError("Source composite too small")
        panels=[]
        for name,(start,end) in [
                ("a_left",(0,width//2)),("b_right",(width//2,width))]:
            box=(start,0,end,height)
            original_panel=original_rgb.crop(box)
            actual_panel=embedded_img.crop(box)
            err=ImageStat.Stat(ImageChops.difference(original_panel,actual_panel))
            mae=sum(err.mean)/(3*255)
            # White-border-tolerant but both panels must contain real imagery.
            nonwhite=sum(1 for pixel in original_panel.resize((32,32)).get_flattened_data()
                         if min(pixel)<235)
            if mae>1/255 or nonwhite<80:
                raise FigurePanelError(f"Composite panel {name} corrupted or empty")
            panels.append({"panel":name,"normalised_rgb_difference":round(mae,8),
                           "nonwhite_thumbnail_pixels":nonwhite,
                           "source_pixel_identity_verified":True,
                           "depicted_object_independently_recognised":False})
    if any(sha(path)!=hashes[key] for key,path in paths.items()):
        raise FigurePanelError("Sources drifted during independent figure QA")
    return {"schema_version":1,"status":"ORIGINAL_TWO_PANEL_FIGURE_PIXEL_IDENTITY_VERIFIED",
        "source_pdf_sha256":hashes["source"],"source_figure_sha256":hashes["figure"],
        "teaching_pdf_sha256":hashes["slides"],"narration_sha256":hashes["narration"],
        "critical_claim_report_sha256":hashes["claims"],
        "original_caption_correlated_with_slide_text":True,
        "narration_panel_names_correlated":True,"panels":panels,
        "full_figure_object_semantics_automatically_proven":False,
        "formal_voice_authorized":False,"provider_calls":0,"publication_allowed":False}

def sha(path):return sha_file(path)

def main(argv=None):
    parser=argparse.ArgumentParser()
    for name in ("source-stage","teaching-slides","narration-qa","claim-audit","new-report"):
        parser.add_argument("--"+name,type=Path,required=True)
    a=parser.parse_args(argv)
    out=a.new_report.resolve(strict=False)
    if (a.new_report.exists() or a.new_report.is_symlink()
        or not out.parent.is_dir()
        or a.source_stage.resolve(strict=True) in out.parents
        or a.teaching_slides.resolve(strict=True) in out.parents
        or any(k.casefold()=="my drive" for k in out.parts)):
        raise FigurePanelError("New external read-only figure report path required")
    r=inspect_serway_figure(a.source_stage,a.teaching_slides,a.narration_qa,a.claim_audit)
    with out.open("x",encoding="utf8") as f:json.dump(r,f,indent=2)
    print(json.dumps({"output":str(out),"panels":len(r["panels"]),
                      "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
