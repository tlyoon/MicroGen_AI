"""Read-only short PCM audio witnesses from original lecture MP4.

Acoustic energy is not phonetic correctness, narrated-word alignment, or academic approval.
No paid services, no media modification and no automatic publication.
"""
from __future__ import annotations
import hashlib,json,math,re,struct,subprocess
from pathlib import Path
from microgen_tts_highlight_evidence import HighlightEvidenceError,validate_manifest,verify_cue_timing,_sha_file,audit_highlight_evidence

class AudioEvidenceError(ValueError):
    pass

SAMPLE_RATE=16000
MAX_MP4_BYTES=12*1024**3

def _finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def validate_audio_window(video, start, seconds, *, duration):
    path=Path(video)
    if path.suffix.lower()!=".mp4" or path.is_symlink() or not path.is_file():
        raise AudioEvidenceError("Existing regular MP4 required")
    size=path.stat().st_size
    if not 0 < size <= MAX_MP4_BYTES:
        raise AudioEvidenceError("Empty or oversized MP4")
    if not all(_finite(v) for v in (start,seconds,duration)):
        raise AudioEvidenceError("Finite audio interval required")
    if not (0 < duration < 600 and 0<=start and 0.05<=seconds<=1.0 and start+seconds<=duration+1e-8):
        raise AudioEvidenceError("Unsafe or out-of-bounds audio window")
    return {"source":str(path),"start_seconds":float(start),"window_seconds":float(seconds),
            "sample_rate":SAMPLE_RATE,"duration_seconds":float(duration)}

def extract_pcm_window(video,start,seconds,*,duration,timeout=25):
    validate_audio_window(video,start,seconds,duration=duration)
    if not _finite(timeout) or not 1<=timeout<=60:
        raise AudioEvidenceError("Invalid FFmpeg timeout")
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-ss",format(start,".6f"),"-i",str(video),"-t",format(seconds,".6f"),
         "-map","0:a:0","-vn","-ac","1","-ar",str(SAMPLE_RATE),
         "-c:a","pcm_s16le","-f","s16le","-fs","40000","pipe:1"]
    try:
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              check=False,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise AudioEvidenceError("Audio FFmpeg subprocess failed") from exc
    raw=result.stdout
    if result.returncode!=0 or not isinstance(raw,bytes) or not 800<=len(raw)<=34000 or len(raw)%2:
        raise AudioEvidenceError("No valid bounded mono PCM output")
    return raw

def pcm_energy(pcm):
    if not isinstance(pcm,bytes) or not 800<=len(pcm)<=34000 or len(pcm)%2:
        raise AudioEvidenceError("Invalid signed PCM16 evidence")
    n=len(pcm)//2
    squares=0; peak=0; clipped=0
    for (value,) in struct.iter_unpack("<h",pcm):
        absval=abs(value);squares+=value*value
        peak=max(peak,absval)
        if absval>=32700:clipped+=1
    return {"sample_count":n,"rms":math.sqrt(squares/n)/32768.0,
            "peak":peak/32768.0,"clipped_fraction":clipped/n,
            "decoded_pcm_sha256":hashlib.sha256(pcm).hexdigest(),
            "spoken_words_verified":False}

def classify_acoustic_activity(metrics,*,rms_floor=.018,clipping_limit=.10):
    if not isinstance(metrics,dict):
        raise AudioEvidenceError("PCM energy metrics required")
    rms=metrics.get("rms");peak=metrics.get("peak");clipped=metrics.get("clipped_fraction")
    if not all(_finite(x) and 0<=x<=1 for x in (rms,peak,clipped)):
        raise AudioEvidenceError("Nonfinite or invalid PCM energy metrics")
    if not _finite(rms_floor) or not _finite(clipping_limit) or not (0<rms_floor<1 and 0<=clipping_limit<1):
        raise AudioEvidenceError("Invalid activity thresholds")
    if clipped>clipping_limit:
        label="UNRELIABLE_CLIPPED_AUDIO"
    elif rms<rms_floor:
        label="BELOW_SPEECH_LIKE_ENERGY_THRESHOLD"
    else:
        label="ACOUSTIC_ENERGY_PRESENT"
    return {"activity_label":label,"acoustic_energy_present":label=="ACOUSTIC_ENERGY_PRESENT",
            "speech_or_phonetic_identity_verified":False}
