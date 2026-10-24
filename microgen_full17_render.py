"""Build full §2.5 staged video from source-bound provisional legacy sound and PDF.

Real 17-slide generation uses 66 cautious ASR/PDF content-word cues.
Audio extracted from historical AAC retains known pronunciation uncertainty.
No original source edits, API calls, Whisper, or release approval.
"""
from __future__ import annotations
from pathlib import Path
import shutil

from microgen_source_safe_orchestrator import (
    OrchestratorError,create_workspace,verify_workspace,stage_existing_root_wavs,
    source_bound_timeline,render_complete_staged_lesson,finalize_staged_parts,
    digest,read_json,atomic_json,
)

class FullRenderError(OrchestratorError):
    pass

def create_full17_render_workspace(proposal,stage):
    data=read_json(proposal)
    if (data.get("status")!="FULL17_PROVISIONAL_AUDIO_TO_PDF_WORD_CUES" or
        data.get("publication_allowed") is not False or
        data.get("slide_count")!=17):
        raise FullRenderError("Verified full lesson cue proposal required")
    previous=Path(data["original_workspace"]).resolve(strict=True)
    source=Path(data["source_root"]).resolve(strict=True)
    from microgen_source_safe_orchestrator import verify_workspace as verify
    old=verify(previous)
    if (old["source_root"]!=str(source) or
        old["source_pdf_sha256"]!=data["original_slide_pdf_sha256"] or
        old["narration_sha256"]!=data["narration_sha256"] or
        digest(source/"slides.mp4")!=data["source_mp4_sha256"]):
        raise FullRenderError("Original media drift or wrong source")
    dest=Path(stage).resolve(strict=False)
    if dest.exists() or dest.is_symlink() or dest==previous or dest.is_relative_to(previous):
        raise FullRenderError("Never overwrite a prior recovery stage")
    if len(data["slides"])!=17 or [x["slide"] for x in data["slides"]]!=list(range(1,18)):
        raise FullRenderError("Invalid numbered slide cues")
    prior=read_json(previous/"legacy_mp4_audio_receipt.json")
    create_workspace(source,dest)
    result=stage_existing_root_wavs(dest)
    if result["copied"] or result["missing"]!=list(range(1,18)):
        raise FullRenderError("Unexpected original source root audio; refuse mixing")
    audio=dest/"audio"
    records=[]
    for row in data["slides"]:
        i=row["slide"]
        p=previous/"audio"/f"slide{i}.wav"
        expected=prior["clips"][i-1]["sha256"]
        if p.is_symlink() or not p.is_file() or expected!=row["audio_sha256"] or digest(p)!=expected:
            raise FullRenderError("Untrusted recovered clip")
        target=audio/p.name
        if target.exists():raise FullRenderError("Refuse prior WAV overwrite")
        shutil.copyfile(p,target)
        if digest(target)!=expected:raise FullRenderError("Copy changed audio SHA")
        records.append({"slide":i,"sha256":expected,
           "source":"source-bound provisional historical AAC scene partition",
           "speaker_authenticated":False})
    atomic_json(dest/"audio_inventory.json",{
         "entries":records,"missing":[],"speech_correctness_verified":False,
         "audio_from_legacy_mp4":True})
    timeline=source_bound_timeline(dest)
    if timeline["slides"]!=17 or not 549<timeline["duration_seconds"]<552:
        raise FullRenderError("Real source lecture timeline unexpected")
    cues=[]
    elapsed=0.
    for row in data["slides"]:
        duration=row["duration_seconds"]
        for item in row["cues"]:
            start,end=item["start_seconds"],item["end_seconds"]
            if not 0<=start<end<=duration+.02:
                raise FullRenderError("Unbounded ASR cue times")
            cues.append({"slide":row["slide"],"text":item["text"],"box":item["box"],
                "start_seconds":round(start+elapsed,6),"end_seconds":round(end+elapsed,6),
                "local_start":start,"local_end":end})
        elapsed+=duration
    if len(cues)!=data["total_cues"]:
        raise FullRenderError("Cue inventory count changed")
    atomic_json(dest/"cues.json",{"version":1,"elements":cues,
        "spoken_word_alignment_verified":False,
        "cue_timestamps_provided_externally":True,
        "mathematics_semantics_verified":False})
    atomic_json(dest/"whole17_provenance.json",{
        "source_mp4_sha256":data["source_mp4_sha256"],
        "provisional_cue_manifest_sha256":digest(proposal),
        "source_recovered_workspace":str(previous),
        "original_source_narration_sha256":data["narration_sha256"],
        "source_wavs_authenticated_original_tts":False,
        "original_pcm_overhang_not_in_17_slide_clips":True,
        "publication_allowed":False})
    verify_workspace(dest)
    return {"workspace":str(dest),"slides":17,"cues":len(cues),
        "audio_seconds":timeline["duration_seconds"],
        "audio_tail_requires_separate_handling":True,"publication_allowed":False}

def render_complete_full17(workspace,*,ffmpeg):
    root=Path(workspace).resolve(strict=True)
    receipt=verify_workspace(root)
    prov=read_json(root/"whole17_provenance.json")
    if prov.get("publication_allowed") is not False:
        raise FullRenderError("Untrusted publishable stage")
    result=render_complete_staged_lesson(root,ffmpeg=ffmpeg)
    if result["rendered_slides"]!=17 or result["true_spoken_alignment_verified"]:
        raise FullRenderError("Incomplete or unverified stage")
    parts=finalize_staged_parts(root,ffmpeg=ffmpeg)
    if (parts["parts"]!=1 or parts["under_600"] is not True or
        parts["release_ready"] is not False):
        raise FullRenderError("Unexpected multipart acceptance")
    final=root/"part01.mp4"
    if not final.is_file():raise FullRenderError("No complete technical movie")
    return {"status":"FULL17_STAGED_TECHNICAL_CANDIDATE",
        "mp4":str(final),"mp4_sha256":digest(final),
        "parts":1,"under_600":True,
        "audio_tail_preserved":False,"pronunciation_verified":False,
        "math_figure_sync_verified":False,
        "publication_allowed":False}
