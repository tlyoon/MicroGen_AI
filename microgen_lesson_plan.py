"""Source-referenced, coherent multipart lecture planner (offline foundation).

A planned part does not certify runtime. The actual final WAV/MP4 duration is
checked separately. Plan is generated before slides/TTS when scene inventory is
available. Does not mechanically cut a finished lecture video.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass,asdict

class PlanningError(ValueError):pass

@dataclass(frozen=True)
class Scene:
    id: str
    topic: str
    source_pages: tuple[int, ...]
    estimated_seconds: float
    natural_break_after: bool = False

@dataclass(frozen=True)
class Part:
    number: int
    scene_ids: tuple[str, ...]
    estimated_seconds: float
    opening: str
    closing: str


def classify_actual_video(seconds: float, *, approved_exception: bool = False) -> str:
    if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<=0:
        raise PlanningError("Actual duration must be positive and finite")
    if seconds<600:return "passed"
    if seconds<630:return "passed_exception" if approved_exception else "review_required"
    return "blocked"


def create_plan(
    scenes: list[Scene], *, intro_seconds=15., outro_seconds=15.,
    target_seconds=510., ceiling_seconds=570.,
) -> dict:
    if not scenes:raise PlanningError("Scene inventory is empty")
    if not (0 < intro_seconds and 0 < outro_seconds and
            0 < target_seconds <= ceiling_seconds < 600 and
            intro_seconds + outro_seconds < ceiling_seconds):
        raise PlanningError("Invalid or unsafe duration budget")
    ids=[s.id for s in scenes]
    if any(not x or not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):
        raise PlanningError("Scene IDs must be unique")
    for s in scenes:
        if not s.topic.strip() or not s.source_pages or any(
            not isinstance(p,int) or isinstance(p,bool) or p<1 for p in s.source_pages
        ):
            raise PlanningError(f"Missing subject-grounding for {s.id}")
        if not math.isfinite(s.estimated_seconds) or s.estimated_seconds<=0:
            raise PlanningError(f"Invalid timing estimate for {s.id}")
        if s.estimated_seconds+intro_seconds+outro_seconds>ceiling_seconds:
            raise PlanningError(f"Indivisible scene {s.id} exceeds the part budget")
    cum=[0.0]
    for s in scenes:cum.append(cum[-1]+s.estimated_seconds)
    n=len(scenes);dp=[float("inf")]*(n+1);prev=[-1]*(n+1);dp[0]=0
    for end in range(1,n+1):
        for start in range(end-1,-1,-1):
            duration=cum[end]-cum[start]+intro_seconds+outro_seconds
            if duration>ceiling_seconds:break
            if not math.isfinite(dp[start]):continue
            score=dp[start]+0.2+((duration-target_seconds)/target_seconds)**2
            if duration<420:score+=((420-duration)/420)**2
            if end!=n and not scenes[end-1].natural_break_after:score+=1.75
            if score<dp[end]:
                dp[end],prev[end]=score,start
    if prev[n]<0:raise PlanningError("Cannot partition scenes without cutting concepts")
    ranges=[];cur=n
    while cur:
        ranges.append((prev[cur],cur));cur=prev[cur]
    ranges.reverse()
    parts=[]
    for number,(a,b) in enumerate(ranges,1):
        first=scenes[a];last=scenes[b-1]
        opening=(f"Connect from {scenes[a-1].topic}; introduce {first.topic}." if a
                 else f"Introduce {first.topic}.")
        closing=(f"Summarize {last.topic}; preview {scenes[b].topic}." if b<n
                 else f"Summarize {last.topic} and conclude.")
        parts.append(Part(number,tuple(s.id for s in scenes[a:b]),
                          round(cum[b]-cum[a]+intro_seconds+outro_seconds,3),
                          opening,closing))
    if [x for p in parts for x in p.scene_ids]!=ids:
        raise PlanningError("Source scenes were omitted or reordered")
    result={"schema_version":1,"scenes":[asdict(s) for s in scenes],
            "parts":[asdict(p) for p in parts],
            "note":"Estimates only; final audio/video must be measured and certified."}
    result["plan_sha256"]=hashlib.sha256(json.dumps(
        result,sort_keys=True,separators=(",",":")
    ).encode()).hexdigest()
    return result
