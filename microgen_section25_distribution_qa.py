"""Technical H.264/AAC delivery-format candidate from fully verified ALAC QA MP4.

Lossy AAC cannot preserve exact PCM SHA by definition. Verify both media
formats, near-matched decoded duration and volume, and strict <600 s.
Distribution and academic/phonetic approval remain independent.
"""
from __future__ import annotations
import math
import re
import subprocess
from pathlib import Path
from microgen_source_safe_orchestrator import (
    OrchestratorError,verify_workspace,read_json,digest,atomic_json
)
from microgen_audio_tail_video_candidate import _decoded_audio_hash
from microgen_quality import check_video

class DeliveryCandidateError(OrchestratorError):
    pass

def _volume(video,ffmpeg):
    command=[str(ffmpeg),"-nostdin","-hide_banner","-i",str(video),
             "-map","0:a:0","-af","volumedetect","-f","null","NUL"]
    try:
        result=subprocess.run(command,capture_output=True,timeout=120)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise DeliveryCandidateError("Cannot analyze decoded volume") from e
    text=result.stderr.decode("utf8","replace")
    matches=re.findall(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB",text)
    if result.returncode or len(matches)!=1:
        raise DeliveryCandidateError("Volume analysis unavailable")
    return float(matches[0])

def make_standard_aac_candidate(workspace,*,ffmpeg):
    root=Path(workspace).resolve(strict=True)
    doc=verify_workspace(root)
    technical=read_json(root/"complete_decoded_pcm_candidate"/"full_pcm_candidate_receipt.json")
    if (technical.get("publication_allowed") is not False or
        technical.get("status")!="COMPLETE_17_SLIDE_PCM_EXACT_TECHNICAL_CANDIDATE" or
        technical.get("all_original_decoded_PCM_samples_preserved") is not True):
        raise DeliveryCandidateError("No verified lossless full-lecture source candidate")
    original=Path(technical["video_path"]).resolve(strict=True)
    if original.is_symlink() or digest(original)!=technical["video_sha256"]:
        raise DeliveryCandidateError("ALAC original QA candidate changed")
    ff=Path(ffmpeg)
    if not ff.is_file():raise DeliveryCandidateError("Explicit FFmpeg binary required")
    dest=root/"standard_h264_aac_candidate"
    if dest.exists() or dest.is_symlink():
        raise DeliveryCandidateError("Refusing to overwrite delivery candidate")
    src_pcm=_decoded_audio_hash(original,ff)
    if abs(src_pcm["pcm_seconds"]-technical["source_audio_seconds"])>.02:
        raise DeliveryCandidateError("Source decoded PCM duration mismatch")
    dest.mkdir()
    target=dest/"section25_h264_aac_192kbps_UNAPPROVED.mp4"
    cmd=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
        "-i",str(original),"-map","0:v:0","-map","0:a:0",
        "-c:v","copy","-c:a","aac","-b:a","192k",
        "-movflags","+faststart",str(target)]
    try:
        outcome=subprocess.run(cmd,capture_output=True,timeout=180)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise DeliveryCandidateError("AAC format conversion failed") from e
    if outcome.returncode or not target.is_file():
        raise DeliveryCandidateError("Unable to encode standard AAC delivery candidate")
    probe=subprocess.run([str(ff),"-hide_banner","-i",str(target)],
                          capture_output=True,timeout=30)
    info=probe.stderr.decode("utf8","replace")
    if not (re.search(r"Video:\s*h264",info,re.I) and re.search(r"Audio:\s*aac",info,re.I)):
        raise DeliveryCandidateError("Unexpected output codec family")
    duration=check_video(target)["seconds"]
    if not 0<duration<600 or abs(duration-technical["video_seconds"])>.2:
        raise DeliveryCandidateError("Converted candidate video violates duration contract")
    final_pcm=_decoded_audio_hash(target,ff)
    if abs(final_pcm["pcm_seconds"]-src_pcm["pcm_seconds"])>.15:
        raise DeliveryCandidateError("Converted AAC cut actual source-audio duration")
    old_db=_volume(original,ff)
    new_db=_volume(target,ff)
    if not math.isfinite(old_db) or not math.isfinite(new_db) or abs(old_db-new_db)>1:
        raise DeliveryCandidateError("AAC conversion unexpectedly changed loudness")
    if digest(original)!=technical["video_sha256"]:
        raise DeliveryCandidateError("Full ALAC technical candidate was changed during conversion")
    verify_workspace(root)
    evidence={"schema_version":1,"status":"H264_AAC_DELIVERY_TECHNICAL_FORMAT_CHECK_PASSED",
        "candidate_mp4_path":str(target),"candidate_mp4_sha256":digest(target),
        "candidate_video_seconds":duration,"video_codec":"h264",
        "audio_codec":"aac","bitrate_target":"192kbps",
        "original_audio_pcm_seconds":src_pcm["pcm_seconds"],
        "candidate_audio_pcm_seconds":final_pcm["pcm_seconds"],
        "source_mean_volume_db":old_db,"candidate_mean_volume_db":new_db,
        "original_lossless_candidate_sha256":technical["video_sha256"],
        "phonetic_QA_verified":False,"mathematical_element_sync_verified":False,
        "consumer_player_independent_acceptance_verified":False,
        "publication_allowed":False,"source_modified":False}
    atomic_json(dest/"format_receipt.json",evidence)
    return {"mp4":str(target),"sha256":evidence["candidate_mp4_sha256"],
        "video_seconds":duration,"audio_codec":"aac","video_codec":"h264",
        "source_duration_diff_seconds":round(final_pcm["pcm_seconds"]-src_pcm["pcm_seconds"],6),
        "source_volume_diff_db":round(new_db-old_db,3),
        "publication_allowed":False}
