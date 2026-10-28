"""Bounded relative alignment of two short-time WAV loudness envelopes.

A geometric/time alignment aid only. NOT a phoneme recognizer.
"""
from __future__ import annotations
import math
from microgen_tts_pcm_features import compare_format

class EnvelopeAlignmentError(ValueError): pass

def align_envelopes(before:dict,after:dict,*,max_lag_seconds:float=2.0,
                    minimum_overlap:float=0.75)->dict:
    compare_format(before,after)
    a=before.get("frame_rms");b=after.get("frame_rms")
    if not isinstance(a,list) or not isinstance(b,list) or min(len(a),len(b))<12:
        raise EnvelopeAlignmentError("Insufficient acoustic samples")
    if not isinstance(max_lag_seconds,(int,float)) or not 0<=max_lag_seconds<=3:
        raise EnvelopeAlignmentError("Invalid bounded lag")
    if not 0.5<=minimum_overlap<=1:
        raise EnvelopeAlignmentError("Invalid overlap fraction")
    frame=before["frame_ms"]/1000
    nlag=min(int(max_lag_seconds/frame),300)
    # Normalize log-energy for gain differences; correlation measures only
    # time-envelope resemblance, not phonetic correctness.
    def transformed(v):
        x=[math.log1p(max(0.0,float(z))*50) for z in v]
        if any(not math.isfinite(z) for z in x):
            raise EnvelopeAlignmentError("Nonfinite energy")
        avg=sum(x)/len(x)
        return [z-avg for z in x]
    x=transformed(a);y=transformed(b)
    results=[]
    for lag in range(-nlag,nlag+1):
        i=max(0,-lag);j=max(0,lag)
        count=min(len(x)-i,len(y)-j)
        if count < minimum_overlap*min(len(x),len(y)):continue
        xx=x[i:i+count];yy=y[j:j+count]
        dot=sum(u*v for u,v in zip(xx,yy))
        norm=math.sqrt(sum(u*u for u in xx)*sum(v*v for v in yy))
        if norm>1e-8:
            results.append((dot/norm,lag,count))
    if not results:
        return {"status":"UNALIGNABLE","lag_seconds":None,"correlation":None,
                "phoneme_verified":False}
    # Deterministic tie: prefer smallest absolute lag then negative lag.
    score,lag,count=sorted(results,key=lambda v:(-v[0],abs(v[1]),v[1]))[0]
    if score<0.55:
        return {"status":"LOW_SIMILARITY_UNALIGNABLE",
                "lag_frames":None,"lag_seconds":None,
                "best_attempted_correlation":round(score,6),
                "before_sha256":before["wav_sha256"],
                "after_sha256":after["wav_sha256"],
                "phoneme_verified":False}
    return {"status":"ENVELOPE_ALIGNMENT_ESTIMATED",
            "lag_frames":lag,"lag_seconds":round(lag*frame,4),
            "correlation":round(max(-1.0,min(1.0,score)),6),
            "overlap_frames":count,"compared_frame_ms":before["frame_ms"],
            "before_sha256":before["wav_sha256"],"after_sha256":after["wav_sha256"],
            "phoneme_verified":False,"alignment_method":"gain_normalized_log_energy_correlation"}
