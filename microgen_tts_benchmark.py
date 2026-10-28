"""Human-labeled, hash-bound real-WAV benchmark for pronunciation screening.

Labels are supplied by real listening observations; unobserved ASR outputs
are always UNKNOWN, never invented. Measurement is conditioned on full
coverage and SHA validation. No source audio is stored in the repository.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

class BenchmarkError(RuntimeError):
    pass

def sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_reference(samples: dict, wav_directory: Path | None=None) -> dict:
    if samples.get("schema_version") != 1 or not isinstance(samples.get("samples"),list):
        raise BenchmarkError("Missing v1 benchmark samples")
    seen=set()
    for sample in samples["samples"]:
        identifier=sample.get("id")
        if not identifier or identifier in seen:
            raise BenchmarkError("Duplicate or empty sample identity")
        seen.add(identifier)
        if sample.get("label") not in ("defect","correct"):
            raise BenchmarkError(f"Unreviewed reference label: {identifier}")
        digest=sample.get("sha256","")
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            raise BenchmarkError(f"Malformed checksum: {identifier}")
        filename=sample.get("filename","")
        if Path(filename).name!=filename or filename in (".",".."):
            raise BenchmarkError("Unsafe reference filename")
        if wav_directory is not None:
            f=wav_directory/filename
            if not f.is_file() or sha256_file(f)!=digest:
                raise BenchmarkError(f"Reference audio checksum mismatch: {identifier}")
    if not any(x["label"]=="defect" for x in samples["samples"]) or not any(
        x["label"]=="correct" for x in samples["samples"]
    ):
        raise BenchmarkError("Both confirmed defect and confirmed correct samples required")
    return {"reference_samples":len(samples["samples"]),
            "reference_audio_verified":wav_directory is not None}

def score_recognition(samples: dict, predictions: dict, *,
                      require_full_coverage: bool=True) -> dict:
    validate_reference(samples)
    lookup={item["id"]:item for item in samples["samples"]}
    if any(k not in lookup for k in predictions):
        raise BenchmarkError("Unknown benchmark identity in predictions")
    if any(v not in ("flag","clear","unknown") for v in predictions.values()):
        raise BenchmarkError("Invalid prediction; must be flag, clear or unknown")
    counts={"TP":0,"TN":0,"FP":0,"FN":0,"UNKNOWN":0}
    rows=[]
    for item in samples["samples"]:
        observed=predictions.get(item["id"],"unknown")
        label=item["label"]
        if observed=="unknown":
            outcome="UNKNOWN"
        elif label=="defect":
            outcome="TP" if observed=="flag" else "FN"
        else:
            outcome="FP" if observed=="flag" else "TN"
        counts[outcome]+=1
        rows.append({"id":item["id"],"reference":label,"prediction":observed,
                     "outcome":outcome})
    scored=sum(counts[k] for k in ("TP","TN","FP","FN"))
    total=len(rows)
    positive=counts["TP"]+counts["FN"]
    negative=counts["TN"]+counts["FP"]
    return {
        "schema_version":1,"sample_count":total,"evaluated":scored,
        "coverage":scored/total,
        "confusion":counts,
        "recall":counts["TP"]/positive if positive else None,
        "false_alarm_rate":counts["FP"]/negative if negative else None,
        "precision":counts["TP"]/(counts["TP"]+counts["FP"])
                    if counts["TP"]+counts["FP"] else None,
        "acceptance_pass": counts["UNKNOWN"]==0 and counts["FN"]==0
                           and counts["FP"]==0 and scored==total,
        "complete":counts["UNKNOWN"]==0,
        "rows":rows,
        "notice":"A benchmark score only describes labeled samples, not real-world error rate.",
    }

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("manifest",type=Path)
    parser.add_argument("--wav-dir",type=Path)
    parser.add_argument("--predictions",type=Path)
    args=parser.parse_args(argv)
    samples=json.loads(args.manifest.read_text(encoding="utf8"))
    metadata=validate_reference(samples,args.wav_dir)
    pred=json.loads(args.predictions.read_text(encoding="utf8")) if args.predictions else {}
    results=score_recognition(samples,pred)
    print(json.dumps({**metadata,**results},indent=2))
    return 0 if results["acceptance_pass"] else 2

if __name__=="__main__":
    raise SystemExit(main())
