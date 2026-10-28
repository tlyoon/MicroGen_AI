"""Read-only energy-based *candidate* speech regions; not word boundaries.

A conservative VAD-like detector operates on SHA-pinned frame RMS and
always labels segments as unverified candidates, never phoneme locations.
"""
from __future__ import annotations
import math
from microgen_tts_pcm_features import pcm_envelope

class RegionError(ValueError): pass

def candidate_regions(envelope:dict,*,floor:float=0.006,
                      relative_floor:float=0.06, min_ms:int=120,
                      bridge_ms:int=100,max_regions:int=400)->dict:
    if (not isinstance(envelope,dict) or
        type(min_ms)!=int or not 40<=min_ms<=1000 or
        type(bridge_ms)!=int or not 0<=bridge_ms<=400 or
        type(max_regions)!=int or not 1<=max_regions<=2000 or
        not isinstance(floor,(float,int)) or not 0<floor<=0.2 or
        not isinstance(relative_floor,(float,int)) or not 0<=relative_floor<=0.4):
        raise RegionError("Invalid conservative region configuration")
    frames=envelope.get("frame_rms")
    frame_ms=envelope.get("frame_ms")
    if not isinstance(frames,list) or not frames or frame_ms not in (10,20,40):
        raise RegionError("Invalid frame measurements")
    if len(frames)>600_000 or any(
        not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in frames):
        raise RegionError("Unbounded or nonfinite frame measurements")
    threshold=max(float(floor),max(frames)*relative_floor)
    is_loud=[x>threshold for x in frames]
    # Merge short inactive islands between two speech-like intervals.
    max_bridge=bridge_ms//frame_ms
    i=0
    while i<len(is_loud):
        if is_loud[i]:i+=1;continue
        j=i
        while j<len(is_loud) and not is_loud[j]:j+=1
        if i>0 and j<len(is_loud) and (j-i)<=max_bridge:
            for k in range(i,j):is_loud[k]=True
        i=j
    needed=max(1,math.ceil(min_ms/frame_ms))
    spans=[];i=0
    while i<len(is_loud):
        if not is_loud[i]:i+=1;continue
        j=i
        while j<len(is_loud) and is_loud[j]:j+=1
        if j-i>=needed:
            spans.append({"start_seconds":round(i*frame_ms/1000,4),
                          "end_seconds":round(min(envelope["duration_seconds"],
                              j*frame_ms/1000),4),
                          "source_frame_start":i,"source_frame_end_exclusive":j,
                          "label":"CANDIDATE_SPEECH_REGION_NOT_VERIFIED"})
        i=j
    if len(spans)>max_regions:
        raise RegionError("Too many regions for bounded QA")
    return {"schema_version":1,"wav_sha256":envelope["wav_sha256"],
            "frame_ms":frame_ms,"threshold_rms":round(threshold,8),
            "candidate_regions":spans,"region_count":len(spans),
            "speech_or_phoneme_labels_verified":False,
            "no_regions_is_clean_audio":False,
            "evidence_class":"UNSUPERVISED_ENERGY_REGIONS"}

def scan_wav(path,**kwargs)->dict:
    return candidate_regions(pcm_envelope(path),**kwargs)
