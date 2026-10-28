"""Verify and unpack an owner-selected free Vosk model without network access.

Only the separately fetched, pinned official English small-model archive is
accepted. Reject zip path escapes and symlinks; never install to protected
teaching folders. Executing this file cannot download anything.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from microgen_source_safe_orchestrator import digest, atomic_json

ARCHIVE_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
MODEL_NAME = "vosk-model-small-en-us-0.15"

class ModelArchiveError(ValueError):
    pass

def unpack_verified_model_archive(archive, destination):
    zip_path = Path(archive).absolute()
    model = Path(destination).absolute()
    if (zip_path.is_symlink() or not zip_path.is_file() or
            digest(zip_path)!=ARCHIVE_SHA256):
        raise ModelArchiveError("Vosk archive absent or SHA-256 not the pinned official model")
    if (model.exists() or model.is_symlink() or
            model==zip_path or model.is_relative_to(zip_path)):
        raise ModelArchiveError("Refuse existing or invalid model destination")
    if model.name != MODEL_NAME:
        raise ModelArchiveError("Vosk extraction must use exact model directory name")
    with zipfile.ZipFile(zip_path) as z:
        infos=z.infolist()
        if not 1<=len(infos)<=500 or sum(x.file_size for x in infos)>250_000_000:
            raise ModelArchiveError("Unbounded archive")
        prepared=[]
        for item in infos:
            raw=item.filename.replace("\\", "/")
            p=PurePosixPath(raw)
            if (p.is_absolute() or any(x in (".","..") for x in p.parts)
                    or not p.parts or p.parts[0]!=MODEL_NAME
                    or len(p.parts)>12 or
                    item.file_size>100_000_000 or
                    stat.S_ISLNK(item.external_attr >> 16)):
                raise ModelArchiveError("Untrusted ZIP entry or path escape")
            if len(p.parts)==1 and not item.is_dir():
                raise ModelArchiveError("Model archive root must be directory")
            prepared.append((item,p))
        model.mkdir(parents=True,exist_ok=False)
        try:
            for item,p in prepared:
                target=model.joinpath(*p.parts[1:])
                if item.is_dir():
                    target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists() or target.is_symlink():
                        raise ModelArchiveError("Duplicate model file path")
                    with z.open(item) as inp,target.open("xb") as out:
                        shutil.copyfileobj(inp,out,length=1024*1024)
                    if target.stat().st_size!=item.file_size:
                        raise ModelArchiveError("Model bytes truncated")
            if not (model/"am"/"final.mdl").is_file():
                raise ModelArchiveError("Acoustic model files missing")
            if digest(zip_path)!=ARCHIVE_SHA256:
                raise ModelArchiveError("Archive mutated during extraction")
        except Exception:
            shutil.rmtree(model)
            raise
    receipt={"status":"PINNED_OFFLINE_VOSK_MODEL_UNAPPROVED_ACOUSTIC_EVIDENCE",
             "model_dir":str(model),"archive_sha256":ARCHIVE_SHA256,
             "files":sum(not it.is_dir() for it,_ in prepared),
             "publication_allowed":False}
    atomic_json(model.parent/"model_provenance.json",receipt)
    return receipt

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",required=True)
    parser.add_argument("--model-dir",required=True)
    args=parser.parse_args()
    print(json.dumps(unpack_verified_model_archive(args.archive,args.model_dir),sort_keys=True))
