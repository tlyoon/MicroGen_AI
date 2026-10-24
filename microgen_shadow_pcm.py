"""Isolated corrected-trial shadow PCM: source-original tail retained.

This is not authorized TTS production. Segment timings change; all old
ASR word cues and frame synchronization MUST be invalidated.
"""
from pathlib import Path
import hashlib,subprocess,wave
from microgen_source_safe_orchestrator import verify_workspace,digest,read_json,atomic_json,OrchestratorError

class ShadowAudioError(OrchestratorError):
    pass

def _pcm(wav,ff):
    command=[str(ff),"-nostdin","-hide_banner","-loglevel","error",
       "-i",str(wav),"-map","0:a:0","-vn","-ac","1","-ar","16000",
       "-c:a","pcm_s16le","-f","s16le","pipe:1"]
    try:
        proc=subprocess.run(command,capture_output=True,timeout=90)
    except (OSError,subprocess.TimeoutExpired) as ex:
        raise ShadowAudioError("Cannot resample bounded trial") from ex
    if proc.returncode or not 3200<len(proc.stdout)<50*32000 or len(proc.stdout)%2:
        raise ShadowAudioError("Corrupt trial or unexpected audio length")
    return proc.stdout

def make_corrected_shadow_pcm(recovery,selection,dest,*,ffmpeg):
    src=Path(recovery).resolve(strict=True)
    selected=Path(selection).resolve(strict=True)
    result=Path(dest).resolve(strict=False)
    receipt=verify_workspace(src)
    if (result.exists() or result.is_symlink() or
        result.is_relative_to(src) or result.is_relative_to(selected) or
        result.is_relative_to(Path(receipt["source_root"]).resolve(strict=True))):
        raise ShadowAudioError("Never overwrite protected or prior audio")
    qa=read_json(selected/"selection_receipt.json")
    if (qa.get("status")!="SHADOW_ONLY_TRIAL_SELECTION" or
        qa.get("publication_allowed") is not False or
        qa.get("source_pdf_sha256")!=receipt["source_pdf_sha256"] or
        qa.get("source_narration_sha256")!=receipt["narration_sha256"]):
        raise ShadowAudioError("Corrected trials not source-bound")
    trial_by_slide={r["slide"]:r for r in qa["trials"]}
    if set(trial_by_slide)!={5,6,10}:
        raise ShadowAudioError("Exactly the source-verified corrections are required")
    legacy=read_json(src/"legacy_mp4_audio_receipt.json")
    ff=Path(ffmpeg)
    if not ff.is_file():raise ShadowAudioError("Explicit local FFmpeg binary required")
    clips=[];total=0.;pieces=[]
    for i in range(1,18):
        if i in trial_by_slide:
            meta=trial_by_slide[i]
            wav=Path(meta["trial_path"]).resolve(strict=True)
            if wav.is_symlink() or digest(wav)!=meta["wav_sha256"]:
                raise ShadowAudioError("Corrected source trial SHA changed")
            label="UNAPPROVED_TRIAL"
        else:
            meta=legacy["clips"][i-1]
            wav=src/"audio"/f"slide{i}.wav"
            if wav.is_symlink() or digest(wav)!=meta["sha256"]:
                raise ShadowAudioError("Recovered source clip SHA changed")
            label="LEGACY_ORIGINAL_AAC_DECODE"
        raw=_pcm(wav,ff)
        seconds=len(raw)/32000
        clips.append({"slide":i,"source":label,"original_sha256":digest(wav),
            "resampled_pcm_sha256":hashlib.sha256(raw).hexdigest(),
            "start_seconds":round(total,6),"duration_seconds":seconds,
            "new_word_timing_required":label=="UNAPPROVED_TRIAL"})
        total+=seconds
        pieces.append(raw)
    tail=src/"audio"/"audio_after_video_end.wav"
    expected=legacy["audio_beyond_video_end"]["tail_sha256"]
    if tail.is_symlink() or digest(tail)!=expected:raise ShadowAudioError("Original audio tail missing")
    extra=_pcm(tail,ff) if tail.stat().st_size>0 else b""
    if not extra:raise ShadowAudioError("Original AAC overhang lost")
    total+=len(extra)/32000
    if not 0<total<570:raise ShadowAudioError("Unsafe shadow lecture duration")
    result.mkdir(parents=True)
    target=result/"section25_corrected_shadow_UNAPPROVED.wav"
    with wave.open(str(target),"wb") as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
        for raw in pieces:out.writeframesraw(raw)
        out.writeframes(extra)
    report={"schema_version":1,"status":"COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM",
        "shadow_wav":str(target),"shadow_sha256":digest(target),
        "audio_seconds":total,"corrected_slides":[5,6,10],
        "audio_segments":clips,"tail_seconds":len(extra)/32000,
        "all_preexisting_ASR_cue_timing_invalidated":True,
        "phonetic_correctness_verified":False,"voice_consistency_verified":False,
        "publication_allowed":False,"source_modified":False}
    atomic_json(result/"shadow_receipt.json",report)
    return {"shadow_pcm":str(target),"duration_seconds":round(total,3),
            "corrections":3,"word_cue_timing_valid":False,"publication_allowed":False}
