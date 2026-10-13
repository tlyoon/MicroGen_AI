"""Collision-safe textbook figure composition with crop provenance.

Gemini maps individual crop paths to destination figure labels. Accumulate
across *all* API batches before writing any destination to prevent a later
response overwriting an earlier panel of the same composite illustration.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageOps


class FigureCompositionError(RuntimeError):
    """Figure cannot be trusted; never silently publish a partial composite."""


def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


class FigureCollector:
    def __init__(self, output_dir: Path):
        self.output_dir=Path(output_dir)
        self.items: dict[str,list[dict]]=defaultdict(list)
        self.sources: dict[str,set[str]]=defaultdict(set)

    def add(self, destination: Path, source: Path, *, source_page: str):
        dst=Path(destination)
        src=Path(source)
        if dst.parent.resolve()!=self.output_dir.resolve():
            raise FigureCompositionError("Destination is outside the owned figure-output directory")
        if not re.fullmatch(r"[A-Za-z0-9 ._()\-]+\.png",dst.name,re.I):
            raise FigureCompositionError(f"Unsafe figure output name: {dst.name!r}")
        if not re.fullmatch(r"page_\d+",source_page):
            raise FigureCompositionError(f"Invalid source page identifier: {source_page}")
        if not src.is_file():
            raise FigureCompositionError(f"Mapped crop is missing: {src}")
        # A filename matched to several *different textbook pages* must be
        # reviewed; this is not permission to combine unrelated textbook figs.
        page_set=self.sources[dst.name.casefold()]
        if page_set and source_page not in page_set:
            raise FigureCompositionError(
                f"Figure label collision across pages: {dst.name}; pages "
                f"{sorted(page_set)} and {source_page}"
            )
        fingerprint=sha256(src)
        entries=self.items[dst.name.casefold()]
        if any(e["source_sha256"]==fingerprint and e["source_page"]==source_page for e in entries):
            return
        with Image.open(src) as image:
            image.verify()
        entries.append({
            "destination":dst.name,"source":str(src.resolve()),
            "source_page":source_page,"source_sha256":fingerprint,
        })
        page_set.add(source_page)

    def finalize(self) -> dict:
        self.output_dir.mkdir(parents=True,exist_ok=True)
        report=[]
        # All input images are checked before writing *any* output.
        for key in sorted(self.items):
            entries=self.items[key]
            page_nums={e["source_page"] for e in entries}
            if len(page_nums)!=1:
                raise FigureCompositionError(f"Cross-page figure collision for {key}")
            for e in entries:
                if sha256(Path(e["source"]))!=e["source_sha256"]:
                    raise FigureCompositionError(f"Figure input changed: {e['source']}")
        for key in sorted(self.items):
            entries=self.items[key]
            dest=self.output_dir/entries[0]["destination"]
            composed=[]
            for entry in entries:
                with Image.open(entry["source"]) as raw:
                    rgb=Image.new("RGB",raw.size,"white")
                    if raw.mode in ("RGBA","LA"):
                        rgba=raw.convert("RGBA")
                        rgb.paste(rgba,mask=rgba.getchannel("A"))
                    else:
                        rgb.paste(raw.convert("RGB"))
                    composed.append(rgb)
            widths=[item.width for item in composed]
            heights=[item.height for item in composed]
            if not widths or min(widths)<2 or min(heights)<2:
                raise FigureCompositionError(f"Invalid cropped panel dimensions for {key}")
            stitched=Image.new("RGB",(sum(widths),max(heights)),"white")
            offsets=[]
            at=0
            for item in composed:
                stitched.paste(item,(at,0))
                offsets.append(at)
                at+=item.width
            candidate=dest.with_name(dest.name+".microgen-candidate.png")
            stitched.save(candidate,format="PNG")
            # Do not alter a previously published different composite silently.
            if dest.is_file() and sha256(dest)!=sha256(candidate):
                candidate.unlink(missing_ok=True)
                raise FigureCompositionError(
                    f"Existing destination conflicts with proposed composite: {dest.name}"
                )
            candidate.replace(dest)
            report.append({
                "destination":dest.name,"output_sha256":sha256(dest),
                "size_pixels":[stitched.width,stitched.height],
                "source_page":entries[0]["source_page"],
                "panel_count":len(composed),"panel_left_offsets_pixels":offsets,
                "source_crops":[{"filename":Path(e["source"]).name,
                                 "sha256":e["source_sha256"]} for e in entries],
                "review_required":(len(composed)>1 or stitched.width / stitched.height>4.0),
            })
        result={"schema_version":1,"figures":report,
                "note":"Crop-composition trace, NOT a scientific/composite-subpanel QA certificate."}
        receipt=self.output_dir/"figure_composition_receipt.json"
        staged=receipt.with_suffix(".json.tmp")
        staged.write_text(json.dumps(result,indent=2),encoding="utf-8")
        staged.replace(receipt)
        return result


def validate_figure_receipt(directory: Path) -> dict:
    directory=Path(directory)
    receipt=directory/"figure_composition_receipt.json"
    if not receipt.is_file():
        raise FigureCompositionError("Figure composition provenance receipt is missing")
    data=json.loads(receipt.read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or not isinstance(data.get("figures"),list):
        raise FigureCompositionError("Invalid figure composition receipt")
    for entry in data["figures"]:
        dest_name=entry.get("destination")
        if not isinstance(dest_name,str) or not re.fullmatch(r"[A-Za-z0-9 ._()\-]+\.png",dest_name,re.I):
            raise FigureCompositionError("Figure receipt contains an unsafe destination path")
        path=directory/dest_name
        if not path.is_file() or sha256(path)!=entry["output_sha256"]:
            raise FigureCompositionError(f"Figure composition changed or missing: {path}")
        if entry["panel_count"]!=len(entry["source_crops"]):
            raise FigureCompositionError("Composite panel count inconsistent with evidence")
    return data
