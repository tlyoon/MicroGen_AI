"""Bounded read-only discovery of authentic local mono PCM16 lecture WAVs."""
from __future__ import annotations
import argparse,json,os,wave
from pathlib import Path
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_identity import decoded_pcm_sha256,PcmIdentityError

class DiscoveryError(ValueError):pass
SKIP={"storage",".git","__pycache__",".venv","node_modules","QA_tts_cdot_20261019"}
def discover_wavs(root:Path,*,max_depth:int=3,max_files:int=80)->dict:
    if (type(max_depth)!=int or not 0<=max_depth<=5 or
        type(max_files)!=int or not 1<=max_files<=200):
        raise DiscoveryError("Invalid bounded discovery configuration")
    base=Path(root).resolve(strict=True)
    if not base.is_dir():raise DiscoveryError("Selected source must be a folder")
    found=[];walked=0;skipped=0
    for here,dirs,files in os.walk(base,followlinks=False):
        directory=Path(here)
        if directory.is_symlink():continue
        walked+=1
        if walked>500:raise DiscoveryError("Directory traversal budget exceeded")
        level=len(directory.relative_to(base).parts)
        dirs[:]=sorted(x for x in dirs if x not in SKIP and
            not (directory/x).is_symlink()) if level<max_depth else []
        for file in sorted(files):
            if not file.lower().endswith(".wav"):continue
            wav=directory/file
            if wav.is_symlink():skipped+=1;continue
            if len(found)>=max_files:
                raise DiscoveryError("WAV discovery limit exceeded")
            if wav.stat().st_size>18_000_000:
                skipped+=1;continue
            try:
                with wave.open(str(wav),"rb") as audio:
                    if (audio.getnchannels()!=1 or audio.getsampwidth()!=2 or
                        audio.getframerate()<8000 or audio.getnframes()<=0):
                        skipped+=1;continue
                    secs=audio.getnframes()/audio.getframerate()
                if secs>600:skipped+=1;continue
                digest=file_sha256(wav)
                pcm=decoded_pcm_sha256(wav)
                if file_sha256(wav)!=digest:
                    skipped+=1
                    continue
            except (OSError,EOFError,wave.Error,ValueError,PcmIdentityError):
                skipped+=1;continue
            found.append({"source_wav":str(wav.resolve(strict=True)),
                          "relative_path":str(wav.relative_to(base)),
                          "source_sha256":digest,"source_pcm_sha256":pcm,
                          "duration_seconds":round(secs,6),
                          "inferred_source_group":str(wav.parent.relative_to(base)),
                          "independent_voice_proven":False,"phoneme_label":None})
    return {"schema_version":1,"root":str(base),"real_wav_candidates":found,
            "candidate_count":len(found),"files_skipped":skipped,
            "discovery_complete":skipped==0,
            "discovery_status":"COMPLETE" if skipped==0 else "PARTIAL_UNINSPECTED_WAVS",
            "independent_source_groups_verified":False,
            "phonetic_ground_truth_available":False,
            "publication_performed":False}
def main(argv=None):
    p=argparse.ArgumentParser(description="Bounded source WAV discovery, read-only")
    p.add_argument("source_root",type=Path);p.add_argument("external_report",type=Path)
    a=p.parse_args(argv)
    root=a.source_root.resolve(strict=True)
    target=a.external_report.resolve(strict=False)
    if (target.exists() or target.is_symlink() or not target.parent.is_dir() or
        target==root or root in target.parents or target in root.parents):
        p.error("Report must be a new path outside source tree")
    report=discover_wavs(root)
    with target.open("x",encoding="utf8") as output:
        json.dump(report,output,indent=2)
    print(json.dumps({"count":report["candidate_count"],"skipped":report["files_skipped"],
                      "labels_verified":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
