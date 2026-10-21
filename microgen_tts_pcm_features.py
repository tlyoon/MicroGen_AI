"""Portable, no-dependency WAV diagnostics and short-time energy envelope.

Quantifies *audio*, not spelling or correctness. No Whisper/NumPy requirement.
Read-only, SHA-256 checked before and after streaming. Memory bounded.
"""
from __future__ import annotations
import array
import hashlib
import math
import sys
import wave
from pathlib import Path

class AcousticFeatureError(ValueError): pass

def file_sha256(path:Path)->str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for part in iter(lambda:handle.read(1<<20),b""):
            digest.update(part)
    return digest.hexdigest()

def pcm_envelope(path:Path,*,frame_ms:int=20,max_seconds:float=600)->dict:
    if type(frame_ms) is not int or frame_ms not in (10,20,40):
        raise AcousticFeatureError("Frame must be 10, 20 or 40 milliseconds")
    if type(max_seconds) not in (int,float) or not 0<max_seconds<=600:
        raise AcousticFeatureError("Invalid duration budget")
    wav=Path(path)
    before=file_sha256(wav)
    with wave.open(str(wav),"rb") as sound:
        rate=sound.getframerate()
        channels=sound.getnchannels()
        width=sound.getsampwidth()
        count=sound.getnframes()
        if channels!=1 or width!=2 or rate<8000 or rate>96000 or count<=0:
            raise AcousticFeatureError("Require nonempty mono signed PCM16 WAV")
        duration=count/rate
        if duration>max_seconds:
            raise AcousticFeatureError("WAV duration exceeds analysis limit")
        points=max(1,round(rate*frame_ms/1000))
        rms=[];zero_fraction=[];clip_fraction=[]
        zero_crossing_fraction=[];mean_abs_pcm_step=[]
        total_square=0;total_count=0
        while total_count<count:
            raw=sound.readframes(min(points,count-total_count))
            values=array.array("h")
            values.frombytes(raw)
            if sys.byteorder!="little":values.byteswap()
            if not values:
                raise AcousticFeatureError("Unexpected incomplete PCM data")
            squares=sum(int(x)*x for x in values)
            n=len(values)
            rms.append(round(math.sqrt(squares/n)/32768,8))
            zero_fraction.append(round(sum(abs(x)<50 for x in values)/n,6))
            clip_fraction.append(round(sum(abs(x)>=32767 for x in values)/n,6))
            crossing=0;step_sum=0
            for previous,current in zip(values,values[1:]):
                if previous*current<0:crossing+=1
                step_sum+=abs(int(current)-previous)
            zero_crossing_fraction.append(round(crossing/max(1,n-1),8))
            mean_abs_pcm_step.append(round(step_sum/max(1,n-1)/65535,8))
            total_square+=squares;total_count+=n
        if total_count!=count:
            raise AcousticFeatureError("WAV frames were truncated")
    if before!=file_sha256(wav):
        raise AcousticFeatureError("WAV changed during acoustic analysis")
    return {"schema_version":1,"wav_sha256":before,"sample_rate_hz":rate,
        "sample_count":count,"duration_seconds":round(duration,6),
        "frame_ms":frame_ms,"frame_samples":points,
        "frame_rms":rms,"frame_zero_fraction":zero_fraction,
        "frame_clipping_fraction":clip_fraction,
        "frame_zero_crossing_fraction":zero_crossing_fraction,
        "frame_mean_abs_step":mean_abs_pcm_step,
        "whole_rms":round(math.sqrt(total_square/total_count)/32768,8),
        "frames":len(rms),"signal_label":"UNCLASSIFIED_ACOUSTIC_MEASUREMENTS",
        "phonetic_correctness_proven":False}

def compare_format(first:dict,second:dict)->dict:
    if first.get("sample_rate_hz")!=second.get("sample_rate_hz") or first.get("frame_ms")!=second.get("frame_ms"):
        raise AcousticFeatureError("Incompatible frame-rate or sampling")
    return {"matching_sample_rate":True,"same_frame_size":True,
            "duration_difference_seconds":round(
               second["duration_seconds"]-first["duration_seconds"],6),
            "phonetic_classification":"NOT_AVAILABLE"}
