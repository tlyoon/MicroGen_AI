"""Memory-bounded PCM audio integrity screen; not pronunciation recognition.

Checks gross silence, clipping, format, duration and padding. Advisories
are not acoustic/human approval. Stream PCM in chunks, never load an entire
textbook lesson into Python sample lists.
"""
from __future__ import annotations
import math
import struct
import wave
from pathlib import Path

class WaveIntegrityError(ValueError):
    pass

def analyze_pcm(path:Path,*,chunk_frames:int=16384,
                threshold:int=64)->dict:
    if chunk_frames<128 or chunk_frames>1000000 or threshold<0:
        raise ValueError("Unsafe PCM analysis configuration")
    samples=0
    sum_sq=0.0
    clipped=0
    quiet_prefix=0
    last_loud=-1
    max_absolute=0
    with wave.open(str(path),"rb") as wav:
        frames=wav.getnframes();rate=wav.getframerate()
        channels=wav.getnchannels();width=wav.getsampwidth()
        if channels!=1 or width!=2 or rate<=0 or frames<=0:
            raise WaveIntegrityError("Expected nonempty mono 16-bit PCM WAV")
        while True:
            data=wav.readframes(chunk_frames)
            if not data:break
            if len(data)%2:
                raise WaveIntegrityError("Truncated PCM frame bytes")
            for (s,) in struct.iter_unpack("<h",data):
                absolute=abs(s)
                sum_sq+=float(s)*s
                max_absolute=max(max_absolute,absolute)
                clipped+=int(absolute>=32767)
                if absolute<=threshold and last_loud==-1:
                    quiet_prefix+=1
                if absolute>threshold:
                    last_loud=samples
                samples+=1
        if samples!=frames:
            raise WaveIntegrityError("Truncated or inconsistent WAV frames")
    duration=samples/rate
    rms=math.sqrt(sum_sq/samples)/32768
    padding_end=0 if last_loud<0 else (samples-last_loud-1)/rate
    metrics={
        "duration_seconds":round(duration,6),
        "rms_fraction_full_scale":round(rms,8),
        "peak_fraction_full_scale":round(max_absolute/32768,8),
        "clipping_fraction":round(clipped/samples,8),
        "leading_quiet_seconds":round(quiet_prefix/rate,5),
        "trailing_quiet_seconds":round(padding_end,5),
        "samples":samples,
    }
    failures=[]
    warnings=[]
    if max_absolute==0:failures.append("digital_silence")
    if duration<0.08:failures.append("implausibly_short_recording")
    if metrics["clipping_fraction"]>0.05:failures.append("severe_clipping")
    if rms<0.002:warnings.append("very_low_signal_level")
    if duration>=8 and quiet_prefix/rate>duration*0.7:
        warnings.append("substantial_leading_silence")
    if duration>=8 and padding_end>duration*0.7:
        warnings.append("substantial_trailing_silence")
    return {
        "valid_pcm_format":True,
        "metrics":metrics,
        "blocking_defects":failures,
        "warnings":warnings,
        "pronunciation_verified":False,
        "listening_approved":False,
    }

def require_structurally_usable_audio(path:Path)->dict:
    report=analyze_pcm(path)
    if report["blocking_defects"]:
        raise WaveIntegrityError(
            "Unusable synthesized audio: "+", ".join(report["blocking_defects"]))
    return report
