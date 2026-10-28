"""Immutable, read-only report of matched before/after TTS audio diagnostics.

A diagnostic report does not authorize acoustic pronunciation clearance,
model selection, technical release, or teaching publication.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from microgen_tts_pcm_features import pcm_envelope,file_sha256
from microgen_tts_acoustic_divergence import rank_divergent_regions

class PairDiagnosticError(ValueError):pass

def analyze_pair(before:Path,after:Path,expected_before:str,expected_after:str)->dict:
    a=Path(before).resolve(strict=True);b=Path(after).resolve(strict=True)
    for value in (expected_before,expected_after):
        if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{64}",value):
            raise PairDiagnosticError("Require exact 64-character SHA-256 pins")
    if a==b:raise PairDiagnosticError("Two distinct source WAVs required")
    if file_sha256(a)!=expected_before or file_sha256(b)!=expected_after:
        raise PairDiagnosticError("Source reference hash mismatch before analysis")
    first=pcm_envelope(a);second=pcm_envelope(b)
    difference=rank_divergent_regions(first,second)
    if file_sha256(a)!=expected_before or file_sha256(b)!=expected_after:
        raise PairDiagnosticError("Source audio changed during pair diagnostics")
    return {
        "schema_version":1,"before_wav_sha256":expected_before,
        "after_wav_sha256":expected_after,
        "before_duration_seconds":first["duration_seconds"],
        "after_duration_seconds":second["duration_seconds"],
        "before_whole_rms":first["whole_rms"],
        "after_whole_rms":second["whole_rms"],
        "before_mean_zero_crossing":round(sum(first["frame_zero_crossing_fraction"])/first["frames"],6),
        "after_mean_zero_crossing":round(sum(second["frame_zero_crossing_fraction"])/second["frames"],6),
        "alignment_status":difference["envelope_alignment"]["status"],
        "alignment_correlation":difference["envelope_alignment"].get(
            "best_attempted_correlation",
            difference["envelope_alignment"].get("correlation")),
        "localization_status":difference["status"],
        "candidate_regions":difference["hotspots"],
        "phonetic_error_detected":None,
        "phonetic_accuracy_certified":False,
        "machine_release_approved":False,
        "human_approval_required":False,
        "production_asset_modified":False,
        "diagnostic_only":True,
        "quality_scope":"Unlabeled amplitude/texture difference; not word or phoneme evidence",
    }

def validate_output(before:Path,after:Path,out:Path)->Path:
    a=Path(before).resolve(strict=True);b=Path(after).resolve(strict=True)
    dest=Path(out).resolve(strict=False)
    if not dest.parent.is_dir() or dest.exists() or dest.is_symlink():
        raise PairDiagnosticError("Report must have a new external path")
    for parent in (a.parent,b.parent):
        if dest==parent or parent in dest.parents or dest in parent.parents:
            raise PairDiagnosticError("Report must be outside source audio directories")
    return dest

def main(argv=None):
    p=argparse.ArgumentParser(description="Immutable diagnostic-only audio comparison")
    p.add_argument("before_wav",type=Path);p.add_argument("after_wav",type=Path)
    p.add_argument("new_external_report",type=Path)
    p.add_argument("--before-sha256",required=True)
    p.add_argument("--after-sha256",required=True)
    args=p.parse_args(argv)
    destination=validate_output(args.before_wav,args.after_wav,args.new_external_report)
    report=analyze_pair(args.before_wav,args.after_wav,
                        args.before_sha256,args.after_sha256)
    with destination.open("x",encoding="utf8") as handle:
        handle.write(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"diagnostic_only":True,"report":str(destination),
                      "alignment":report["alignment_status"],
                      "localization":report["localization_status"]}))
    return 0
if __name__=="__main__":raise SystemExit(main())
