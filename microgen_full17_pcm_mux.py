"""Full highlighted Thomas §2.5 QA video with all source decoded PCM samples.

Use lossless ALAC and final-frame hold to preserve the verified 1.023 s AAC
overhang. Neither PCM equality nor timed word boxes is phonetic, academic,
voice-consistency, or mathematical semantic certification.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess

from microgen_source_safe_orchestrator import (
    OrchestratorError,verify_workspace,read_json,digest,atomic_json
)
from microgen_audio_tail_video_candidate import _assemble_verified_pcm_master,_decoded_audio_hash
from microgen_quality import check_video

class FullPCMError(OrchestratorError):
    pass

def remux_full_lecture_with_all_source_pcm(workspace,*,ffmpeg):
    stage=Path(workspace).resolve(strict=True)
    source_receipt=verify_workspace(stage)
    prior=read_json(stage/"whole17_provenance.json")
    source=Path(source_receipt["source_root"])
    old=Path(prior["source_recovered_workspace"]).resolve(strict=True)
    if old==stage or source in stage.parents or stage in source.parents:
        raise FullPCMError("Unsafe source/staging relationship")
    old_receipt=verify_workspace(old)
    if (old_receipt["source_pdf_sha256"]!=source_receipt["source_pdf_sha256"]
        or old_receipt["narration_sha256"]!=source_receipt["narration_sha256"]
        or digest(source/"slides.mp4")!=prior["source_mp4_sha256"]):
        raise FullPCMError("Original source/provisional WAV receipt mismatch")
    recovered=read_json(old/"legacy_mp4_audio_receipt.json")
    if (recovered.get("status")!="PROVISIONAL_NOT_PUBLISHABLE" or
        recovered.get("scene_evidence",{}).get("mp4_sha256")!=prior["source_mp4_sha256"] or
        recovered.get("audio_beyond_video_end",{}).get("requires_review") is not True):
        raise FullPCMError("Verified original AAC tail missing")
    part=stage/"part01.mp4"
    result=read_json(stage/"parts_receipt.json")
    if (not part.is_file() or part.is_symlink() or not result["all_parts_strictly_under_600"]
        or len(result["parts"])!=1 or digest(part)!=result["parts"][0]["sha256"]):
        raise FullPCMError("Complete 17-slide highlighted part not authenticated")
    if not Path(ffmpeg).is_file():
        raise FullPCMError("Explicit FFmpeg local executable required")
    finaldir=stage/"complete_decoded_pcm_candidate"
    if finaldir.exists() or finaldir.is_symlink():
        raise FullPCMError("Never overwrite a complete candidate")
    original_audio=_decoded_audio_hash(source/"slides.mp4",ffmpeg)
    video=check_video(part)
    tail=recovered["audio_beyond_video_end"]["tail_seconds"]
    if not .05<=tail<=3 or not 0<video["seconds"]<600:
        raise FullPCMError("Video/source AAC duration unsafe")
    finaldir.mkdir()
    master=finaldir/"source_pcm_master.wav"
    assembled=_assemble_verified_pcm_master(old,recovered,master)
    if assembled!=original_audio:
        raise FullPCMError("Slide WAVs plus preserved tail do not equal source PCM")
    expected=original_audio["pcm_seconds"]
    if not 0<expected<570 or abs((video["seconds"]+tail)-expected)>.40:
        raise FullPCMError("Visual duration/source PCM clock differs")
    output=finaldir/"section25_full17_ASR_HIGHLIGHTS_ALAC_QA_ONLY.mp4"
    video_pad=max(0.,expected-video["seconds"])+.70
    command=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error","-n",
          "-i",str(part),"-i",str(master),"-map","0:v:0","-map","1:a:0",
          "-vf",f"tpad=stop_mode=clone:stop_duration={video_pad:.6f}",
          "-c:v","libx264","-preset","ultrafast","-crf","25",
          "-pix_fmt","yuv420p","-c:a","alac","-t",f"{expected:.6f}",
          "-movflags","+faststart",str(output)]
    try:
        proc=subprocess.run(command,capture_output=True,timeout=240)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise FullPCMError("Full highlighted technical remux timed out") from e
    if proc.returncode or not output.is_file():
        raise FullPCMError("FFmpeg source PCM remux failed: "+
                            proc.stderr.decode("utf8","replace")[-350:])
    actual_video=check_video(output)
    if actual_video["seconds"]>=600 or abs(actual_video["seconds"]-expected)>.30:
        raise FullPCMError("Final full video duration violates original decoded PCM")
    candidate_audio=_decoded_audio_hash(output,ffmpeg)
    if candidate_audio!=original_audio:
        raise FullPCMError("Lossless candidate decoded audio is not bit-identical")
    if digest(source/"slides.mp4")!=prior["source_mp4_sha256"]:
        raise FullPCMError("Historical source video mutated during remux")
    verify_workspace(stage)
    receipt={"schema_version":1,
       "status":"COMPLETE_17_SLIDE_PCM_EXACT_TECHNICAL_CANDIDATE",
       "video_path":str(output),"video_sha256":digest(output),
       "video_seconds":actual_video["seconds"],
       "source_mp4_sha256":prior["source_mp4_sha256"],
       "source_decoded_pcm_sha256":original_audio["pcm_sha256"],
       "candidate_decoded_pcm_sha256":candidate_audio["pcm_sha256"],
       "source_audio_seconds":expected,
       "preserved_audio_tail_seconds":tail,
       "all_original_decoded_PCM_samples_preserved":True,
       "source_video_unchanged":True,
       "word_semantic_sync_verified":False,
       "phonetic_QA_verified":False,
       "academic_math_QA_verified":False,
       "ALAC_only_technical_QA":True,
       "publication_allowed":False}
    atomic_json(finaldir/"full_pcm_candidate_receipt.json",receipt)
    return {"video":str(output),"sha256":receipt["video_sha256"],
       "duration_seconds":actual_video["seconds"],
       "preserved_audio_tail_seconds":tail,
       "decoded_audio_pcm_exact_match":True,"publication_allowed":False}
