"""Evidence-bound multipart video delivery for split STEM lessons.

Technical content hashes, durations and decoded-audio QA only.
Never infer mathematical correctness or narration-to-figure alignment.
"""
from __future__ import annotations
import hashlib
import json
import wave
from pathlib import Path

from microgen_fresh_source_cues import source_inventory
from microgen_tts_video_duration_inventory import audit_videos
from microgen_source_safe_orchestrator import digest


class MultipartEvidenceError(ValueError):
    pass


def verify_multipart_delivery(stage, receipt_path, independent_av_receipt):
    base, source = source_inventory(stage)
    master=Path(receipt_path).resolve(strict=True)
    qa=Path(independent_av_receipt).resolve(strict=True)
    if (master.is_symlink() or qa.is_symlink() or
            master.parent==base or master.is_relative_to(base) or
            qa.is_relative_to(base)):
        raise MultipartEvidenceError("Independent read-only delivery evidence required")
    receipt=json.loads(master.read_text(encoding="utf8"))
    audit=json.loads(qa.read_text(encoding="utf8"))
    if (receipt.get("source")!=source or audit.get("source")!=source or
        receipt.get("source_pdf_sha256")!=source["slides_pdf_sha256"] or
        receipt.get("publication_allowed") is not False or
        audit.get("publication_allowed") is not False or
        receipt.get("spoken_equation_figure_semantics_verified") is not False or
        audit.get("mathematical_figure_alignment_verified") is not False):
        raise MultipartEvidenceError("Source or release status inconsistent")
    parts=receipt.get("parts")
    qa_parts=audit.get("parts")
    if (not isinstance(parts,list) or not 1<=len(parts)<=20 or
        not isinstance(qa_parts,list) or len(qa_parts)!=len(parts) or
        audit.get("full_pcm_hash_matches") is not True):
        raise MultipartEvidenceError("Incomplete independent multipart evidence")
    paths=[]
    start=1
    used=set()
    for index,(part,check) in enumerate(zip(parts,qa_parts),1):
        bound=part.get("slides")
        if (part.get("part")!=index or check.get("part")!=index or
            not isinstance(bound,list) or len(bound)!=2 or
            not all(type(x) is int for x in bound) or
            bound[0]!=start or bound[1]<bound[0] or bound[1]>source["slide_count"]):
            raise MultipartEvidenceError("Non-contiguous slide coverage")
        expected=[s["wav_sha256"] for s in source["wav_inventory"][bound[0]-1:bound[1]]]
        if part.get("input_wav_sha256")!=expected:
            raise MultipartEvidenceError("Individual source WAVs differ from delivery")
        start=bound[1]+1
        name=part.get("video_file")
        pcm_name=part.get("audio_file")
        if (not isinstance(name,str) or Path(name).name!=name or
            not name.lower().endswith(".mp4") or
            not isinstance(pcm_name,str) or Path(pcm_name).name!=pcm_name or
            not pcm_name.lower().endswith(".wav")):
            raise MultipartEvidenceError("Unsafe multipart filenames")
        video=master.parent/name
        pcm=master.parent/pcm_name
        if (video in used or video.is_symlink() or not video.is_file() or
            pcm.is_symlink() or not pcm.is_file()):
            raise MultipartEvidenceError("Missing, duplicate, or untrusted media part")
        used.add(video)
        if (digest(video)!=part.get("video_sha256") or
            check.get("mp4_sha256")!=part.get("video_sha256") or
            check.get("decoded_audio_pcm_sha256")!=part.get("raw_audio_pcm_sha256")):
            raise MultipartEvidenceError("Video or decoded audio provenance drift")
        with wave.open(str(pcm),"rb") as stream:
            if stream.getnchannels()!=1 or stream.getsampwidth()!=2:
                raise MultipartEvidenceError("Invalid source PCM encoding")
            samples=stream.readframes(stream.getnframes())
        if hashlib.sha256(samples).hexdigest()!=part.get("raw_audio_pcm_sha256"):
            raise MultipartEvidenceError("Original assembled PCM changed")
        paths.append(video)
    if start!=source["slide_count"]+1:
        raise MultipartEvidenceError("Missing final slides")
    videos=audit_videos(paths)
    if (not videos["all_videos_under_600_seconds"] or
        len({r["video_sha256"] for r in videos["videos"]})!=len(parts)):
        raise MultipartEvidenceError("Invalid multipart technical duration")
    for part,row in zip(parts,videos["videos"]):
        if row["video_sha256"]!=part["video_sha256"] or abs(row["duration_seconds"]-part["seconds"])>.25:
            raise MultipartEvidenceError("Video duration/source drift")
    return {"technical_multipart_av_pass":True,"part_count":len(parts),
            "part_durations":[p["duration_seconds"] for p in videos["videos"]],
            "all_part_durations_below_600":True,
            "original_source_wav_count":source["slide_count"],
            "delivery_receipt_sha256":digest(master),"independent_qa_sha256":digest(qa),
            "source_pdf_sha256":source["slides_pdf_sha256"],
            "audio_pcm_source_match":True,
            "academic_semantics_verified":False,
            "narration_to_equation_or_figure_sync_verified":False,
            "publication_allowed":False}
