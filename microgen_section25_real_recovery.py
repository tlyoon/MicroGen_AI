"""Fail-closed recovery of the known Thomas §2.5 lecture into isolated Dell storage.

Original production and cloned source files are read-only; the historical
material is copied only after checking the recorded SHA-256 fingerprints.
Correction trials remain UNAPPROVED. No model download/API/Whisper/publication.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from microgen_source_safe_orchestrator import digest, create_workspace, stage_existing_root_wavs
from microgen_legacy_audio_demux import recover_legacy_scene_wavs, inspect_legacy_scene_receipt
from microgen_audio_tail_video_candidate import render_audio_tail_candidate
from microgen_section25_pronunciation_review import make_section25_review_bundle
from microgen_correction_selection import select_source_bound_trials
from microgen_corrected_audio_stage import prepare_section25_corrected_wavs
from microgen_shadow_pcm import make_corrected_shadow_pcm

EXPECTED = {
    "slides.pdf": "775abbaee3bd54a9885894ada4b5347fdc05a0a36aa278fc8420fe5b1406bc30",
    "slides.mp4": "7d27d24d5d6a7ae5bf05cfcef1ea324d628abcf70688437a5555ac1c85b7e9f8",
    "script_tts.json": "f645222f0c2acb2a57ce038995c8152bdacc086804733f417d34ab1e64d6b56b",
    "source.pdf": "dbc34b5de194c3eedcfc686dfabacc903cc45d858b7a5240912a358d2f2f384b",
}
EXTRAS = (
    ".microgen_legacy_video_evidence.json",
    "QA_tts_cdot_20261019/qa_receipt.json",
    "QA_tts_cdot_20261019/slide5_corrected.wav",
    "QA_tts_cdot_20261019/slide6_corrected.wav",
    "QA_tts_y_20261019/qa_receipt.json",
    "QA_tts_y_20261019/slide10_corrected_y.wav",
    "QA_tts_PR35_20261020/repair_receipt.json",
    "QA_tts_PR35_20261020/slide10_PR35_unapproved.wav",
    "QA_tts_PR39_20261020/all_slide_listening_queue.json",
)
class Section25RecoveryError(ValueError):
    pass

def _files_all_preserved(inventory):
    for path, sha in inventory:
        if path.is_symlink() or not path.is_file() or digest(path) != sha:
            raise Section25RecoveryError("Protected historical input changed during copy")

def mirror_known_lecture(cloned_source_pdf, production, destination):
    """Fingerprint before any copy; never overwrite or write in either input tree."""
    cloned=Path(cloned_source_pdf).absolute()
    source=Path(production).resolve(strict=True)
    dest=Path(destination).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or source.is_symlink()
        or dest == source or dest.is_relative_to(source) or source.is_relative_to(dest)
        or dest == cloned or dest.is_relative_to(cloned.parent)
        or cloned.parent.is_relative_to(dest)):
        raise Section25RecoveryError("Unsafe or existing independent source mirror")
    if cloned.is_symlink() or not cloned.is_file() or digest(cloned)!=EXPECTED["source.pdf"]:
        raise Section25RecoveryError("Cloned source PDF not the agreed Thomas §2.5 original")
    copy_plan=[(cloned,Path("source.pdf"))]
    for name in (*[x for x in EXPECTED if x!="source.pdf"],*EXTRAS):
        file=source/Path(name)
        if file.is_symlink() or not file.is_file() or not file.resolve(strict=True).is_relative_to(source):
            raise Section25RecoveryError("Required historical evidence missing or linked: "+name)
        if name in EXPECTED and digest(file)!=EXPECTED[name]:
            raise Section25RecoveryError("Historical media differs from independent receipt: "+name)
        copy_plan.append((file,Path(name)))
    if (source/"source.pdf").is_file() and digest(source/"source.pdf")!=EXPECTED["source.pdf"]:
        raise Section25RecoveryError("Archived source PDF differs from the clone")
    fingerprints=[(file,digest(file)) for file,_ in copy_plan]
    for name in EXPECTED:
        if name=="source.pdf":continue
        if digest(source/name)!=EXPECTED[name]:
            raise Section25RecoveryError("Source drift before staging")
    dest.mkdir(parents=True)
    try:
        for file,rel in copy_plan:
            target=dest/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() or target.is_symlink():
                raise Section25RecoveryError("No source-mirror overwrite permitted")
            shutil.copyfile(file,target)
            if digest(target)!=digest(file):
                raise Section25RecoveryError("Copied file not byte-identical")
        _files_all_preserved(fingerprints)
        record={"status":"HISTORICAL_SECTION25_SOURCE_MIRROR_UNAPPROVED",
                "known_production_hashes":EXPECTED,
                "copied_inputs":[{"relative_path":str(rel),"sha256":digest(file)}
                    for file,rel in copy_plan],
                "source_modified":False,"originals_read_only":True,
                "phonetic_correctness_verified":False,
                "publication_allowed":False}
        (dest/"recovery_mirror_manifest.json").write_text(
            json.dumps(record,indent=2,sort_keys=True),encoding="utf8")
    except Exception:
        shutil.rmtree(dest)
        raise
    return {"mirrored":len(copy_plan),"source_mirror":str(dest),
            "publication_allowed":False}

def require_tail_ffmpeg_capabilities(executable):
    """Refuse old FFmpeg binaries without tpad *before* writing media."""
    path=Path(executable)
    if not path.is_file() or path.is_symlink():
        raise Section25RecoveryError("Regular local FFmpeg executable required")
    try:
        probe=subprocess.run(
            [str(path),"-hide_banner","-filters"],
            capture_output=True,text=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Section25RecoveryError("Cannot safely inspect local FFmpeg filters") from exc
    if probe.returncode or not any(
        len(row.split())>=2 and row.split()[1]=="tpad"
        for row in probe.stdout.splitlines()):
        raise Section25RecoveryError("FFmpeg lacks tpad: use a verified existing newer binary")
    return path


def stage_recovered_original(source_mirror, recovery_stage, ffmpeg):
    if Path(recovery_stage).exists():raise Section25RecoveryError("Prior recovery stage")
    create_workspace(source_mirror,recovery_stage)
    first=stage_existing_root_wavs(recovery_stage)
    if first["copied"] or first["missing"]!=list(range(1,18)):
        raise Section25RecoveryError("Source has unexpectedly mixed root WAVs")
    source=inspect_legacy_scene_receipt(recovery_stage)
    result=recover_legacy_scene_wavs(recovery_stage,ffmpeg=ffmpeg)
    if result["wav_count"]!=17 or result["ready_for_publication"] is not False:
        raise Section25RecoveryError("Incomplete recovered original audio")
    return {"source_sha256":source["mp4_sha256"],**result}

def main(argv=None):
    p=argparse.ArgumentParser(description="Isolated original Thomas §2.5 evidence recovery; no publication")
    p.add_argument("step",choices=["mirror","recover","tail","review","select","corrected","shadow"])
    p.add_argument("--clone-pdf",type=Path)
    p.add_argument("--production",type=Path)
    p.add_argument("--campaign",type=Path,required=True)
    p.add_argument("--ffmpeg",type=Path)
    p.add_argument("--source-decode-ffmpeg",type=Path)
    args=p.parse_args(argv)
    campaign=args.campaign.resolve(strict=False)
    if campaign.is_symlink():
        raise Section25RecoveryError("Refuse linked output campaign")
    if args.step=="mirror":
        if not args.clone_pdf or not args.production or campaign.exists():
            raise Section25RecoveryError("Source clone/production and unused campaign required")
        campaign.mkdir(parents=True)
        result=mirror_known_lecture(args.clone_pdf,args.production,campaign/"source_mirror")
    else:
        if not campaign.is_dir():raise Section25RecoveryError("Existing isolated campaign required")
        source=campaign/"source_mirror"
        recovery=campaign/"recovery"
        if args.step=="recover":
            if not args.ffmpeg:raise Section25RecoveryError("Explicit ffmpeg required")
            result=stage_recovered_original(source,recovery,args.ffmpeg)
        elif args.step=="tail":
            if not args.ffmpeg:raise Section25RecoveryError("Explicit ffmpeg required")
            ff=require_tail_ffmpeg_capabilities(args.ffmpeg)
            result=render_audio_tail_candidate(
                recovery,ffmpeg=ff,source_decoder_ffmpeg=args.source_decode_ffmpeg)
        elif args.step=="review":
            result=make_section25_review_bundle(recovery,campaign/"review")
        elif args.step=="select":
            result=select_source_bound_trials(recovery,campaign/"review",campaign/"selection")
        elif args.step=="corrected":
            result=prepare_section25_corrected_wavs(
                recovery,campaign/"selection",campaign/"corrected_stage")
        else:
            if not args.ffmpeg:raise Section25RecoveryError("Explicit ffmpeg required")
            result=make_corrected_shadow_pcm(
                recovery,campaign/"selection",campaign/"shadow_pcm",ffmpeg=args.ffmpeg)
    print(json.dumps({"operation":args.step,"evidence":result,"publication_allowed":False},sort_keys=True,default=str))
    return 0  # technical workflow completed; NEVER a publication authorization

if __name__=="__main__":
    raise SystemExit(main())
