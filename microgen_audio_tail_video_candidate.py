"""Nonpublishing candidate: extend final visual slide to retain verified AAC overhang.

The original mp4 is read-only. Verified AAC-decoded PCM is preserved in a
lossless master and re-encoded as ALAC for this QA-only MP4. A decoded PCM
SHA-256 check must match the source exactly. Rendering success
does NOT certify pronunciation, mathematics, or highlighted-word timing.
"""
from __future__ import annotations
import hashlib
import subprocess
from pathlib import Path

from microgen_quality import check_video
from microgen_legacy_audio_demux import LegacyRecoveryError,inspect_legacy_scene_receipt
from microgen_source_safe_orchestrator import digest,read_json,verify_workspace,atomic_json

def _decoded_audio_hash(video,ffmpeg):
    cmd=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error",
       "-i",str(video),"-map","0:a:0","-vn","-ac","1","-ar","16000",
       "-f","s16le","pipe:1"]
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=120)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise LegacyRecoveryError("Cannot decode audio for bit identity QA") from e
    raw=p.stdout
    if p.returncode or not 1000<=len(raw)<=40_000_000 or len(raw)%2:
        raise LegacyRecoveryError("Invalid decoded PCM for audio identity QA")
    return {"pcm_sha256":hashlib.sha256(raw).hexdigest(),
            "pcm_samples":len(raw)//2,"pcm_seconds":len(raw)/32000}

def _assemble_verified_pcm_master(root, receipt, output):
    """Concatenate the staged 17 slices and separately preserved end tail.

    Verify every input WAV SHA. No original source media is ever written.
    """
    import wave
    clips=receipt.get("clips")
    if not isinstance(clips,list) or not clips or [c.get("slide") for c in clips]!=list(range(1,len(clips)+1)):
        raise LegacyRecoveryError("Unordered PCM clips in prior scene receipt")
    tail=receipt.get("audio_beyond_video_end",{})
    inputs=[(root/"audio"/f"slide{c['slide']}.wav",c["sha256"]) for c in clips]
    inputs.append((root/"audio"/"audio_after_video_end.wav",tail.get("tail_sha256")))
    hasher=hashlib.sha256()
    samples=0
    with wave.open(str(output),"wb") as master:
        master.setnchannels(1)
        master.setsampwidth(2)
        master.setframerate(16000)
        for path,sha in inputs:
            if not isinstance(sha,str) or not path.is_file() or path.is_symlink() or digest(path)!=sha:
                raise LegacyRecoveryError("Staged source WAV checksum mismatch")
            with wave.open(str(path),"rb") as src:
                if (src.getnchannels()!=1 or src.getsampwidth()!=2 or
                    src.getframerate()!=16000):
                    raise LegacyRecoveryError("Incompatible decoded PCM slice")
                raw=src.readframes(src.getnframes())
            hasher.update(raw)
            samples+=len(raw)//2
            master.writeframes(raw)
    return {"pcm_sha256":hasher.hexdigest(),"pcm_samples":samples,
            "pcm_seconds":samples/16000}


def render_audio_tail_candidate(workspace,*,ffmpeg):
    root=Path(workspace).resolve(strict=True)
    verify_workspace(root)
    evidence=inspect_legacy_scene_receipt(root)
    receipt=read_json(root/"legacy_mp4_audio_receipt.json")
    if (receipt.get("version")!=1 or receipt.get("status")!="PROVISIONAL_NOT_PUBLISHABLE"
        or receipt.get("scene_evidence",{}).get("mp4_sha256")!=evidence["mp4_sha256"]
        or receipt.get("publication_allowed") is not False):
        raise LegacyRecoveryError("Staged original AAC recovery receipt missing or changed")
    tail=receipt.get("audio_beyond_video_end")
    if not isinstance(tail,dict):
        raise LegacyRecoveryError("Independent AAC overhang evidence required")
    seconds=tail.get("tail_seconds")
    if type(seconds) not in (int,float) or not .05<=seconds<=3.0:
        raise LegacyRecoveryError("Bounded positive audio overhang required")
    tailwav=root/"audio"/"audio_after_video_end.wav"
    if (not tailwav.is_file() or tailwav.is_symlink() or
        digest(tailwav)!=tail.get("tail_sha256")):
        raise LegacyRecoveryError("Source AAC tail WAV fingerprint differs")
    target=evidence["actual_duration_seconds"]+seconds
    if target>=599.5:
        raise LegacyRecoveryError("Candidate cannot meet strict 600-second limit")
    ff=Path(ffmpeg)
    if not ff.is_file():raise LegacyRecoveryError("Explicit local FFmpeg executable required")
    video=Path(evidence["mp4_path"])
    before=digest(video)
    if before!=evidence["mp4_sha256"]:
        raise LegacyRecoveryError("Historical video changed")
    directory=root/"technical_candidate_lossless_timed"
    if directory.exists() or directory.is_symlink():
        raise LegacyRecoveryError("Refuse overwrite of prior candidate")
    # Decode beforehand for a grounded audio identity baseline.
    original_pcm=_decoded_audio_hash(video,ff)
    if abs(original_pcm["pcm_seconds"]-target)>.12:
        raise LegacyRecoveryError("Overhang receipt does not match decoded AAC samples")
    directory.mkdir()
    master=directory/"original_decoded_pcm_master.wav"
    assembled=_assemble_verified_pcm_master(root,receipt,master)
    if assembled!=original_pcm:
        raise LegacyRecoveryError("Staged PCM clips do not reproduce original AAC audio exactly")
    output=directory/"slides_full_audio_ALAC_NOT_PUBLISHED.mp4"
    # Video is re-encoded because tpad needs to clone the final visible frame.
    # Lossless ALAC uses decoded original PCM, not AAC edit-list packet timing.
    cmd=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
         "-i",str(video),"-i",str(master),"-map","0:v:0","-map","1:a:0",
         "-vf",f"tpad=stop_mode=clone:stop_duration={seconds+.4:.6f}",
         "-c:v","libx264","-preset","ultrafast","-crf","28",
         "-pix_fmt","yuv420p","-c:a","alac","-t",f"{target:.6f}",
         "-movflags","+faststart",str(output)]
    try:
        run=subprocess.run(cmd,capture_output=True,timeout=240)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise LegacyRecoveryError("Video tail render could not complete") from e
    if run.returncode or not output.is_file():
        raise LegacyRecoveryError("Video tail render failed: "+run.stderr.decode("utf8","replace")[-350:])
    actual=check_video(output)
    if not 0<actual["seconds"]<600 or abs(actual["seconds"]-target)>.35:
        raise LegacyRecoveryError("Video tail length does not match genuine AAC endpoint")
    candidate_pcm=_decoded_audio_hash(output,ff)
    if candidate_pcm!=original_pcm:
        raise LegacyRecoveryError("Original AAC speech changed during candidate mux")
    if digest(video)!=before:
        raise LegacyRecoveryError("Historical source mutated during render")
    verify_workspace(root)
    result={"status":"TECHNICAL_END_FRAME_EXTENSION_NOT_PUBLISHABLE",
      "original_mp4_sha256":before,"candidate_mp4_sha256":digest(output),
      "candidate_path":str(output),
      "original_video_seconds":evidence["actual_duration_seconds"],
      "full_audio_seconds":candidate_pcm["pcm_seconds"],
      "candidate_video_seconds":actual["seconds"],
      "tail_retained_seconds":seconds,
      "decoded_audio_pcm_sha256_unchanged":True,
      "candidate_audio_codec":"ALAC lossless (QA-only compatibility)",
      "general_publication_format_approved":False,
      "visual_final_slide_held":True,
      "spoken_word_sync_verified":False,"pronunciation_verified":False,
      "academic_review_verified":False,"publication_allowed":False,
      "historical_source_modified":False}
    atomic_json(root/"technical_tail_candidate_receipt.json",result)
    return result
