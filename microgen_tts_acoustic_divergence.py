"""Read-only bounded local acoustic divergence ranking, with abstention.

Requires demonstrably comparable short-time envelopes. No word alignment,
phoneme labels, or automated defect/publishability verdict is ever derived.
"""
from __future__ import annotations
import math
from microgen_tts_envelope_alignment import align_envelopes

class DivergenceError(ValueError):pass

def rank_divergent_regions(first:dict,second:dict, *,
                           window_seconds:float=0.5,step_seconds:float=0.25,
                           max_candidates:int=8)->dict:
    if (type(max_candidates) is not int or not 1<=max_candidates<=12 or
        not isinstance(window_seconds,(float,int)) or not 0.2<=window_seconds<=2 or
        not isinstance(step_seconds,(float,int)) or not 0.1<=step_seconds<=window_seconds):
        raise DivergenceError("Invalid bounded hotspot configuration")
    alignment=align_envelopes(first,second)
    base={"schema_version":1,
          "before_sha256":first["wav_sha256"],"after_sha256":second["wav_sha256"],
          "envelope_alignment":alignment,"phonetic_error_identified":False,
          "publication_approved":False}
    if alignment["status"]!="ENVELOPE_ALIGNMENT_ESTIMATED":
        return {**base,"status":"ABSTAIN_INSUFFICIENT_ALIGNMENT",
                "hotspots":[],"diagnostic_only":True}
    n=first["frame_rms"];m=second["frame_rms"]
    features=("frame_rms","frame_zero_crossing_fraction","frame_mean_abs_step")
    for key in features:
        if (key not in first or key not in second or
            len(first[key])!=len(n) or len(second[key])!=len(m)):
            raise DivergenceError(f"Incomplete time-local audio measurements: {key}")
    frame=first["frame_ms"]/1000
    width=max(2,round(window_seconds/frame))
    stride=max(1,round(step_seconds/frame))
    lag=alignment["lag_frames"]
    i=max(0,-lag);j=max(0,lag)
    length=min(len(n)-i,len(m)-j)
    if length<width:return {**base,"status":"ABSTAIN_TOO_SHORT","hotspots":[],"diagnostic_only":True}
    gain_a=max(0.0001,sum(n)/len(n))
    gain_b=max(0.0001,sum(m)/len(m))
    values=[]
    for k in range(length):
        a=i+k;b=j+k
        left=n[a]/gain_a;right=m[b]/gain_b
        energy=abs(left-right)/max(1.,left,right)
        crossings=abs(first["frame_zero_crossing_fraction"][a]-
                      second["frame_zero_crossing_fraction"][b])
        steps=abs(first["frame_mean_abs_step"][a]-
                  second["frame_mean_abs_step"][b])
        values.append(0.5*energy+0.3*crossings+0.2*min(1.,steps*10))
    ranked=[]
    for start in range(0,length-width+1,stride):
        score=sum(values[start:start+width])/width
        if not math.isfinite(score):raise DivergenceError("Non-finite divergence")
        ranked.append({"first_start_s":round((i+start)*frame,4),
                       "second_start_s":round((j+start)*frame,4),
                       "duration_s":round(width*frame,4),
                       "relative_acoustic_divergence":round(score,6)})
    ranked.sort(key=lambda x:(-x["relative_acoustic_divergence"],x["first_start_s"]))
    # Suppress overlapping windows to emphasize independent candidate regions.
    chosen=[]
    for item in ranked:
        if all(abs(item["first_start_s"]-x["first_start_s"])>=window_seconds
               for x in chosen):
            chosen.append(item)
        if len(chosen)>=max_candidates:break
    return {**base,"status":"LOCAL_ACOUSTIC_DIFFERENCES_ONLY",
            "hotspots":chosen,"diagnostic_only":True,
            "note":"Regions are nonlinguistic audio differences; not y/yay or word locations"}
