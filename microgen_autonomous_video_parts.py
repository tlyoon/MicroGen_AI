"""Autonomous <600s lecture segmentation using verified per-slide media.

Designed for insertion into the original MicroGen_AI gen_video_v22 final
assembly. Only cuts BETWEEN complete slides; every input media cache key,
source WAV, slide and H264/AAC output is hash-bound. No manual scene review.
This stage cannot repair inaccurate science or audio, only split good media.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from microgen_quality import QualityError, sha256, check_video, check_wavs, numbered_files

RECEIPT=".microgen_autonomous_parts.json"
MAX_TARGET_SECONDS=545.0
MAX_OUTPUT_SECONDS=600.0


class AutoPartsError(QualityError):
    pass


def _keys(stage: Path, count: int) -> dict:
    names=["source.pdf","slides.pdf","slides.mp4","script_tts.json"]
    names += [f"slide{i}.pdf" for i in range(1,count+1)]
    names += [f"slide{i}.wav" for i in range(1,count+1)]
    from microgen_timed_highlight_contract import MANIFEST,inspect_timed_highlights
    if (stage/MANIFEST).exists():
        evidence=inspect_timed_highlights(stage)
        if evidence["slide_count"]!=count:
            raise AutoPartsError("Timed highlight slide count mismatch")
        names.append(MANIFEST)
        rows=json.loads((stage/MANIFEST).read_text(encoding="utf8"))["slides"]
        names += [cue["audio_chunk"] for row in rows for cue in row["cues"]]
    return {name:sha256(stage/name) for name in names}


def _cache_segments(stage: Path, count: int) -> list[Path]:
    from microgen_timed_highlight_contract import (
        MANIFEST,inspect_timed_highlights,video_segment_cache_key,
    )
    timed=(inspect_timed_highlights(stage) if (stage/MANIFEST).exists()
           else None)
    if timed is not None and timed["slide_count"]!=count:
        raise AutoPartsError("Highlight timing slide count mismatch")
    result=[]
    cache=(stage/".microgen_video_cache" if timed is None else
           stage/f".microgen_video_cache_timed_{timed['manifest_sha256'][:12]}")
    for i in range(1,count+1):
        path=cache/f"slide{i}.mp4"
        meta=cache/f"slide{i}.json"
        if not path.is_file() or path.is_symlink() or not meta.is_file() or meta.is_symlink():
            raise AutoPartsError("Missing or unsafe source-bound per-slide video cache")
        actual=json.loads(meta.read_text(encoding="utf8"))
        key=video_segment_cache_key(
            stage/f"slide{i}.pdf",stage/f"slide{i}.wav",
            timed["manifest_sha256"] if timed is not None else None,
        )
        if actual.get("key")!=key or actual.get("sha256")!=sha256(path):
            raise AutoPartsError("Per-slide video cache is stale or spoofed")
        check_video(path)
        result.append(path)
    return result


def plan_parts(durations: list[float], titles: list[str]|None=None,
               *, max_seconds: float=MAX_TARGET_SECONDS) -> list[list[int]]:
    """Minimize number of parts; secondarily choose balanced topic boundaries."""
    if not 0 < max_seconds < MAX_OUTPUT_SECONDS:
        raise AutoPartsError("Unsafe segment maximum")
    n=len(durations)
    if not 1 <= n <= 200 or any(
        not math.isfinite(v) or v<=0 or v>max_seconds for v in durations):
        raise AutoPartsError("Uncuttable or invalid slide WAV duration")
    labels=titles if titles is not None else [""]*n
    if len(labels)!=n:
        raise AutoPartsError("Titles and slide count disagree")
    prefix=[0.0]
    for duration in durations:
        prefix.append(prefix[-1]+duration)
    dp=[None]*(n+1)
    dp[0]=(0,0.0,[])
    for j in range(1,n+1):
        for i in range(j):
            elapsed=prefix[j]-prefix[i]
            if elapsed>max_seconds:
                continue
            if dp[i] is None:
                continue
            count,cost,groups=dp[i]
            # A title transition is a convenient boundary, never proof of
            # semantic correctness. Content remains slide-exact either way.
            same_next=(j<n and labels[j-1].strip()
                       and labels[j-1].strip().casefold()==labels[j].strip().casefold())
            penalty=((elapsed-0.72*max_seconds)/max_seconds)**2
            if same_next:
                penalty+=0.07
            candidate=(count+1,cost+penalty,groups+[list(range(i+1,j+1))])
            if dp[j] is None or candidate[:2]<dp[j][:2]:
                dp[j]=candidate
    if dp[n] is None:
        raise AutoPartsError("No whole-slide segmentation below duration ceiling")
    groups=dp[n][2]
    if [x for part in groups for x in part]!=list(range(1,n+1)):
        raise AutoPartsError("Automatic segment plan duplicates or loses slides")
    return groups


def verify_receipt(stage: Path) -> dict:
    stage=Path(stage)
    p=stage/RECEIPT
    if p.is_symlink() or not p.is_file():
        raise AutoPartsError("Missing verified autonomous video parts receipt")
    receipt=json.loads(p.read_text(encoding="utf8"))
    if (receipt.get("schema_version")!=1 or
        receipt.get("validation")!="verified_slide_boundary_parts" or
        receipt.get("publication_allowed") is not False):
        raise AutoPartsError("Invalid automatic parts receipt")
    parts=receipt.get("parts")
    if not isinstance(parts,list) or not parts or len(parts)>100:
        raise AutoPartsError("Invalid video parts inventory")
    count=sum(len(x.get("slides",[])) for x in parts)
    wavs=check_wavs(stage,count)
    expected=_keys(stage,count)
    if receipt.get("source_media_sha256")!=expected:
        raise AutoPartsError("Source or WAV changed after segment acceptance")
    _cache_segments(stage,count)
    flattened=[]
    for i,part in enumerate(parts,1):
        if (part.get("index")!=i or
            part.get("file")!=f"slides_part_{i:02d}.mp4" or
            not isinstance(part.get("slides"),list) or
            not part["slides"] or
            part.get("boundary_kind")!="whole_slide" or
            part.get("sha256")!=sha256(stage/part["file"])):
            raise AutoPartsError("Video part order, name, boundary or hash mismatch")
        expected_secs=sum(wavs["seconds"][s-1] for s in part["slides"]
                          if type(s) is int and 1<=s<=count)
        if expected_secs<=0 or expected_secs>MAX_TARGET_SECONDS:
            raise AutoPartsError("Bad part timing or slide indices")
        actual=check_video(stage/part["file"],expected_seconds=expected_secs)
        if actual["seconds"]>=MAX_OUTPUT_SECONDS:
            raise AutoPartsError("Output part exceeds strict 600-second policy")
        flattened.extend(part["slides"])
    if flattened!=list(range(1,count+1)):
        raise AutoPartsError("Parts omit or repeat slides")
    if len(parts)>1 and not all(part["slides"] for part in parts):
        raise AutoPartsError("Empty part")
    return receipt


def render_if_needed(stage: Path, concat) -> dict|None:
    """Render all new parts in private temporary scratch then commit last.

    Idempotent on current content. Never overwrites an existing partial/stale
    media part or an old protected full slides.mp4.
    """
    stage=Path(stage)
    import fitz
    with fitz.open(stage/"slides.pdf") as pdf:
        count=pdf.page_count
    wavs=check_wavs(stage,count)
    full=check_video(stage/"slides.mp4",expected_seconds=wavs["total_seconds"])
    if full["seconds"]<MAX_OUTPUT_SECONDS:
        return None
    existing=stage/RECEIPT
    if existing.exists() or existing.is_symlink():
        return verify_receipt(stage)
    sources=_keys(stage,count)
    segments=_cache_segments(stage,count)
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if (len(slides)!=count or
        [x.get("slide") for x in slides]!=list(range(1,count+1))):
        raise AutoPartsError("Narration and source slide order mismatch")
    titles=[str(x.get("title") or "") for x in slides]
    groups=plan_parts(wavs["seconds"],titles)
    if len(groups)<2:
        raise AutoPartsError("Long full video not actually split")
    for index in range(1,len(groups)+1):
        name=stage/f"slides_part_{index:02d}.mp4"
        if name.exists() or name.is_symlink():
            raise AutoPartsError("Refusing to replace an existing video part")
    if _keys(stage,count)!=sources:
        raise AutoPartsError("Source changed before video-part rendering")
    with tempfile.TemporaryDirectory(prefix=".microgen-auto-parts-",dir=stage) as td:
        scratch=Path(td)
        pieces=[]
        for index,ids in enumerate(groups,1):
            candidate=scratch/f"slides_part_{index:02d}.mp4"
            concat([segments[s-1] for s in ids],candidate)
            secs=sum(wavs["seconds"][s-1] for s in ids)
            actual=check_video(candidate,expected_seconds=secs)
            if actual["seconds"]>=MAX_OUTPUT_SECONDS:
                raise AutoPartsError("Candidate video part exceeds 600 seconds")
            pieces.append({
                "index":index,"file":candidate.name,
                "slides":ids,"boundary_kind":"whole_slide",
                "expected_wav_seconds":round(secs,4),
                "actual_seconds":actual["seconds"],
                "sha256":sha256(candidate),
            })
        if _keys(stage,count)!=sources:
            raise AutoPartsError("Source changed during video rendering")
        created=[]
        try:
            for piece in pieces:
                target=stage/piece["file"]
                os.replace(scratch/piece["file"],target)
                created.append(target)
            receipt={
                "schema_version":1,"validation":"verified_slide_boundary_parts",
                "source_media_sha256":sources,"parts":pieces,
                "automatic":True,"human_approval_is_gate":False,
                "publication_allowed":False,
            }
            existing.write_text(json.dumps(receipt,indent=2),encoding="utf8")
            verify_receipt(stage)
            return receipt
        except Exception:
            existing.unlink(missing_ok=True)
            for target in created:
                target.unlink(missing_ok=True)
            raise
