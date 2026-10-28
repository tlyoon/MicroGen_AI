"""Nonpublishing §2.5 corrected trial shadow video; no word cues or approvals.

Combine verified full shadow PCM with historical picture after extending its
last still. Exact decoded PCM equality and source checks are mandatory.
"""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import wave
from pathlib import Path
from microgen_source_safe_orchestrator import digest, read_json, atomic_json, verify_workspace
from microgen_audio_tail_video_candidate import _decoded_audio_hash
from microgen_quality import check_video
from microgen_section25_real_recovery import require_tail_ffmpeg_capabilities

class CorrectedShadowVideoError(ValueError):
    pass

def _pcm_properties(path):
    with wave.open(str(path), "rb") as f:
        if (f.getnchannels(), f.getsampwidth(), f.getframerate()) != (1,2,16000):
            raise CorrectedShadowVideoError("Shadow audio must be mono 16k PCM16")
        count=f.getnframes()
        raw=f.readframes(count)
    if len(raw)!=count*2 or not 1<count<600*16000:
        raise CorrectedShadowVideoError("Unsafe or truncated shadow PCM")
    return {"pcm_sha256":hashlib.sha256(raw).hexdigest(),
            "pcm_samples":count,"pcm_seconds":count/16000}

def render_corrected_shadow_video(recovery, selection, shadow, dest, *, ffmpeg):
    """Fail closed, leave historic MP4 and existing trial WAVs unchanged."""
    rec=Path(recovery).resolve(strict=True)
    sel=Path(selection).resolve(strict=True)
    sh=Path(shadow).resolve(strict=True)
    receipt=verify_workspace(rec)
    source=Path(receipt["source_root"]).resolve(strict=True)
    out=Path(dest).resolve(strict=False)
    protect=(rec,sel,sh,source)
    if (out.exists() or out.is_symlink() or
            any(out==p or out.is_relative_to(p) or p.is_relative_to(out)
                for p in protect)):
        raise CorrectedShadowVideoError("Output must be new and separate from source")
    if receipt["slide_count"]!=17:
        raise CorrectedShadowVideoError("17-slide grounded source required")
    legacy=read_json(rec/"legacy_mp4_audio_receipt.json")
    select=read_json(sel/"selection_receipt.json")
    report=read_json(sh/"shadow_receipt.json")
    video=source/"slides.mp4"
    wav=sh/"section25_corrected_shadow_UNAPPROVED.wav"
    if video.is_symlink() or wav.is_symlink() or not video.is_file() or not wav.is_file():
        raise CorrectedShadowVideoError("Source or shadow WAV absent/symlinked")
    original_sha=digest(video)
    if (legacy.get("status")!="PROVISIONAL_NOT_PUBLISHABLE" or
            legacy.get("scene_evidence",{}).get("mp4_sha256")!=original_sha or
            select.get("status")!="SHADOW_ONLY_TRIAL_SELECTION" or
            select.get("publication_allowed") is not False or
            select.get("source_pdf_sha256")!=receipt["source_pdf_sha256"] or
            select.get("source_narration_sha256")!=receipt["narration_sha256"] or
            select.get("source_mp4_sha256")!=original_sha or
            sorted([r.get("slide") for r in select.get("trials",[])])!=[5,6,10] or
            report.get("status")!="COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM" or
            report.get("publication_allowed") is not False or
            report.get("all_preexisting_ASR_cue_timing_invalidated") is not True or
            report.get("corrected_slides")!=[5,6,10] or
            report.get("shadow_sha256")!=digest(wav) or
            Path(report.get("shadow_wav","")).resolve()!=wav):
        raise CorrectedShadowVideoError("Current source/selection/shadow evidence not bound")
    segments=report.get("audio_segments")
    if (not isinstance(segments,list) or len(segments)!=17 or
            [row.get("slide") for row in segments]!=list(range(1,18)) or
            any(row.get("new_word_timing_required") is not (row["slide"] in {5,6,10})
                for row in segments)):
        raise CorrectedShadowVideoError("Corrupt audio-segment inventory")
    originals=legacy.get("clips")
    if not isinstance(originals,list) or len(originals)!=17:
        raise CorrectedShadowVideoError("Incomplete original audio evidence")
    by_trial={r["slide"]:r for r in select["trials"]}
    for row in segments:
        i=row["slide"]
        expected=(by_trial[i]["wav_sha256"] if i in by_trial
                  else originals[i-1]["sha256"])
        if row.get("original_sha256")!=expected:
            raise CorrectedShadowVideoError("Correction or original clip has changed")
    pcm=_pcm_properties(wav)
    seconds=pcm["pcm_seconds"]
    if abs(seconds-report["audio_seconds"])>0.001 or not 0<seconds<600:
        raise CorrectedShadowVideoError("Incorrect 600-second lecture clock")
    ff=require_tail_ffmpeg_capabilities(ffmpeg)
    picture=check_video(video,ffmpeg=str(ff))["seconds"]
    if not 0< picture <seconds<600 or seconds-picture>10:
        raise CorrectedShadowVideoError("Inconsistent historical video length")
    # No generic narration/video release: render a still-frame-extended trial
    # to inspect corrections independently, *without* claiming word highlights.
    out.mkdir(parents=True,exist_ok=False)
    candidate=out/"section25_corrected_shadow_NO_HIGHLIGHT_NOT_PUBLISHED.mp4"
    try:
        cmd=[str(ff),"-nostdin","-hide_banner","-loglevel","error","-n",
             "-i",str(video),"-i",str(wav),"-map","0:v:0","-map","1:a:0",
             "-vf",f"tpad=stop_mode=clone:stop_duration={seconds-picture+.4:.6f}",
             "-c:v","libx264","-preset","ultrafast","-crf","28",
             "-pix_fmt","yuv420p","-c:a","alac","-t",f"{seconds:.6f}",
             "-movflags","+faststart",str(candidate)]
        run=subprocess.run(cmd,capture_output=True,timeout=240)
        if run.returncode or not candidate.is_file():
            raise CorrectedShadowVideoError("Corrected technical render failed: "+run.stderr.decode("utf8","replace")[-250:])
        actual=check_video(candidate,ffmpeg=str(ff))["seconds"]
        if not 0<actual<600 or abs(actual-seconds)>.35:
            raise CorrectedShadowVideoError("Video length differs from corrected PCM")
        decoded=_decoded_audio_hash(candidate,ff)
        if decoded!=pcm:
            raise CorrectedShadowVideoError("Decoded video audio differs from corrected shadow PCM")
        if digest(video)!=original_sha or digest(wav)!=report["shadow_sha256"] or verify_workspace(rec)!=receipt:
            raise CorrectedShadowVideoError("Source changed while rendering")
        record={"status":"CORRECTED_SHADOW_VISUAL_CANDIDATE_UNAPPROVED",
                "source_mp4_sha256":original_sha,"shadow_wav_sha256":report["shadow_sha256"],
                "candidate_mp4_sha256":digest(candidate),
                "corrected_audio_pcm_sha256":pcm["pcm_sha256"],
                "corrected_audio_samples":pcm["pcm_samples"],
                "video_seconds":actual,"audio_seconds":seconds,
                "corrected_slides":[5,6,10],"source_decoded_audio_overhang_retained":True,
                "all_old_word_timing_invalid":True,"highlight_cues_present":False,
                "pronunciation_verified":False,"voice_verified":False,
                "math_figure_sync_verified":False,"publication_allowed":False}
        atomic_json(out/"corrected_shadow_video_receipt.json",record)
        return {"candidate":str(candidate),"duration_seconds":actual,
                "exact_corrected_pcm_preserved":True,"publication_allowed":False}
    except Exception:
        shutil.rmtree(out)
        raise
