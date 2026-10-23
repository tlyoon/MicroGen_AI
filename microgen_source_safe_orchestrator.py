"""Bounded, source-pinned original MicroGen_AI lecture rendering workspaces.

This is a staging tool, not automatic permission to publish, and it never
calls a fee-bearing synthesis API. PDF geometry does not prove semantic
narration alignment. Source MP4 cannot be used as a WAV provenance oracle.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,shutil,tempfile,wave
from pathlib import Path
import pymupdf as fitz

class OrchestratorError(ValueError):
    pass

def digest(p):
    hasher=hashlib.sha256()
    with Path(p).open("rb") as inp:
        for chunk in iter(lambda:inp.read(1024*1024),b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def read_json(p):
    def unique(items):
        output={}
        for k,v in items:
            if k in output:raise OrchestratorError("Duplicate JSON field")
            output[k]=v
        return output
    return json.loads(Path(p).read_text(encoding="utf8"),object_pairs_hook=unique)

def atomic_json(p,contents):
    p=Path(p)
    temp=p.with_name(p.name+".new")
    if temp.exists():raise OrchestratorError("Unclean interrupted JSON write")
    try:
        temp.write_text(json.dumps(contents,sort_keys=True,indent=2),encoding="utf8")
        os.replace(temp,p)
    finally:
        if temp.exists():temp.unlink()

def source_audio_inventory(source):
    from microgen_pipeline_completion import production_contract
    src=Path(source).resolve(strict=True)
    contract=production_contract(src)
    rows=[]
    for i in range(1,contract["slide_count"]+1):
        p=src/f"slide{i}.wav"
        if p.is_symlink():raise OrchestratorError("Source WAV symlink rejected")
        rows.append({"slide":i,"present":p.is_file(),
             "sha256":digest(p) if p.is_file() else None})
    return {"contract":contract,"slides":rows,
        "missing":[r["slide"] for r in rows if not r["present"]],
        "wave_provenance_verified":False,"original_assets_modified":False}
