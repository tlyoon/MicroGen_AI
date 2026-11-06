"""Private all-or-nothing production of new >600s PCM-timed lecture deliverables.

Uses the existing source/WAV/cue contract, hash-bound segment cache, autonomous
slide-boundary planner, real H264/AAC probe, and independent decoded-frame QA.
No existing accepted media, source input, or previous result is overwritten.

All assets are staged by same-volume hard links under an isolated stage.
Independent QA runs on the *actual candidate delivery parts* before promotion.
No semantic, phonetic, scientific or publication rights are certified here.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from microgen_autonomous_video_parts import (
    RECEIPT as PARTS_RECEIPT, MAX_OUTPUT_SECONDS, MAX_TARGET_SECONDS,
    _cache_segments, _keys, plan_parts, verify_receipt as verify_parts,
)
from microgen_measured_highlight_video_qa import (
    RECEIPT as VISUAL_RECEIPT, audit_stage as visual_audit,
    verify_receipt as verify_visual,
)
from microgen_quality import check_video, check_wavs, sha256
from microgen_timed_highlight_contract import MANIFEST, inspect_timed_highlights


class TimedLongTransactionError(RuntimeError):
    """Timed long-video commit refused; no unsafe media replacement."""


JOURNAL=".microgen_timed_long_pending.json"


def _link(source: Path, destination: Path) -> None:
    """Exclusive creation: neither a symlink nor an existing file can be reused."""
    if source.is_symlink() or not source.is_file():
        raise TimedLongTransactionError(f"Missing or unsafe source: {source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, destination)


def _input_inventory(stage: Path, count: int, manifest: dict) -> dict[str, str]:
    names=["source.pdf", "slides.pdf", "script_tts.json", MANIFEST]
    names += [f"slide{i}.pdf" for i in range(1,count+1)]
    names += [f"slide{i}.wav" for i in range(1,count+1)]
    raw=json.loads((stage/MANIFEST).read_text(encoding="utf8"))
    names += [cue["audio_chunk"] for slide in raw["slides"]
              for cue in slide["cues"]]
    cache=f".microgen_video_cache_timed_{manifest['manifest_sha256'][:12]}"
    for i in range(1,count+1):
        names.extend((f"{cache}/slide{i}.mp4",f"{cache}/slide{i}.json"))
    if len(names)!=len(set(names)):
        raise TimedLongTransactionError("Duplicate timed-lecture input path")
    inventory={}
    for name in names:
        path=stage/name
        if path.is_symlink() or not path.is_file():
            raise TimedLongTransactionError(f"Unavailable hash-bound input: {name}")
        inventory[name]=sha256(path)
    return inventory


def recover_timed_long(stage: Path, *, ffmpeg: Path) -> str:
    """Recover interrupted installation only if every existing byte is ours.

    Journal is written after decoded-video QA and before the first no-replace
    link. Never touch unrecognized, modified or existing accepted media.
    """
    stage=Path(stage)
    journal=stage/JOURNAL
    if not journal.exists() and not journal.is_symlink():
        return "no_pending_transaction"
    if journal.is_symlink() or not journal.is_file():
        raise TimedLongTransactionError("Unsafe pending transaction journal")
    try:
        state=json.loads(journal.read_text(encoding="utf8"))
        if (state.get("schema_version")!=1 or
                state.get("publication_allowed") is not False or
                not isinstance(state.get("input_sha256"),dict) or
                not isinstance(state.get("output_sha256"),dict)):
            raise TimedLongTransactionError("Invalid pending transaction")
        expected=state["output_sha256"]
        names=list(expected)
        parts=[name for name in names if name.startswith("slides_part_")]
        canonical=["slides.mp4"]+[
            f"slides_part_{i:02d}.mp4" for i in range(1,len(parts)+1)
        ]+[PARTS_RECEIPT,VISUAL_RECEIPT]
        if (names!=canonical or not 2<=len(parts)<=100 or
                any(not isinstance(value,str) or len(value)!=64
                    for value in expected.values())):
            raise TimedLongTransactionError("Unsafe pending output inventory")
        from microgen_timed_highlight_contract import HighlightContractError
        try:
            timed=inspect_timed_highlights(stage)
        except HighlightContractError as exc:
            raise TimedLongTransactionError(
                "Source changed since interrupted transaction") from exc
        if _input_inventory(stage,timed["slide_count"],timed)!=state["input_sha256"]:
            raise TimedLongTransactionError("Source changed since interrupted transaction")
        present=[]
        for name in names:
            path=stage/name
            if path.is_symlink() or (path.exists() and
                    (not path.is_file() or sha256(path)!=expected[name])):
                raise TimedLongTransactionError(
                    "Unrelated or modified media is protected from recovery")
            if path.exists():
                present.append(path)
        if len(present)==len(names):
            verify_parts(stage)
            verify_visual(stage,ffmpeg=ffmpeg)
            journal.unlink()
            return "completed_verified_transaction"
        for path in reversed(present):
            path.unlink()
        journal.unlink()
        return "rolled_back_incomplete_transaction"
    except (KeyError, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        if isinstance(exc,TimedLongTransactionError):
            raise
        raise TimedLongTransactionError(
            "Cannot safely recover interrupted timed media") from exc


def promote_timed_long(stage: Path, segments: list[Path], candidate: Path,
                       concat, *, ffmpeg: Path) -> dict:
    """Commit a fully verified, new long lecture with no replacement.

    Only fresh output paths are legal. Previously accepted static/full media
    or incomplete parts are never overwritten. Any failure during install
    removes only files created by *this* invocation, in reverse order.
    """
    stage=Path(stage)
    candidate=Path(candidate)
    ffmpeg=Path(ffmpeg)
    if not stage.is_dir() or stage.is_symlink() or not ffmpeg.is_file():
        raise TimedLongTransactionError("Use isolated real stage and FFmpeg")
    if candidate.is_symlink() or not candidate.is_file():
        raise TimedLongTransactionError("Missing complete private MP4 candidate")
    if (stage/JOURNAL).exists() or (stage/JOURNAL).is_symlink():
        raise TimedLongTransactionError(
            "Unrecovered pending timed transaction; run recovery first")
    timed=inspect_timed_highlights(stage)
    count=timed["slide_count"]
    wavs=check_wavs(stage,count)
    whole=check_video(candidate,expected_seconds=wavs["total_seconds"])
    if whole["seconds"]<MAX_OUTPUT_SECONDS:
        raise TimedLongTransactionError("Timed transaction only handles long media")
    if len(segments)!=count:
        raise TimedLongTransactionError("Missing per-slide timed MP4 segments")
    # Catch a preexisting accepted or incomplete destination before making
    # any new part; do not silently reinterpret it as a new timed render.
    if any((stage/name).exists() or (stage/name).is_symlink()
           for name in ("slides.mp4",PARTS_RECEIPT,VISUAL_RECEIPT)):
        raise TimedLongTransactionError("Previous final media or QA evidence is protected")
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if len(slides)!=count or [row.get("slide") for row in slides]!=list(range(1,count+1)):
        raise TimedLongTransactionError("Source narration and slide order disagree")
    names=[str(x.get("title") or "") for x in slides]
    groups=plan_parts(wavs["seconds"],names)
    if len(groups)<2 or len(groups)>100:
        raise TimedLongTransactionError("Long archive requires bounded whole-slide parts")
    piece_names=[f"slides_part_{i:02d}.mp4" for i in range(1,len(groups)+1)]
    if any((stage/name).exists() or (stage/name).is_symlink()
           for name in piece_names):
        raise TimedLongTransactionError("Existing video part is protected")
    cached=_cache_segments(stage,count)
    if [sha256(x) for x in segments]!=[sha256(x) for x in cached]:
        raise TimedLongTransactionError("Rendering cache differs from verified source")
    snapshot=_input_inventory(stage,count,timed)
    with tempfile.TemporaryDirectory(prefix=".microgen-timed-long-",dir=stage) as directory:
        shadow=Path(directory)
        for filename in snapshot:
            _link(stage/filename,shadow/filename)
        _link(candidate,shadow/"slides.mp4")
        parts=[]
        for i,ids in enumerate(groups,1):
            name=piece_names[i-1]
            output=shadow/name
            concat([shadow/f".microgen_video_cache_timed_{timed['manifest_sha256'][:12]}"/
                    f"slide{slide}.mp4" for slide in ids],output)
            seconds=sum(wavs["seconds"][slide-1] for slide in ids)
            checked=check_video(output,expected_seconds=seconds)
            if (checked["seconds"]>=MAX_OUTPUT_SECONDS
                    or abs(checked["seconds"]-seconds)>1.0):
                raise TimedLongTransactionError("Candidate part exceeds limit or PCM clock drift")
            parts.append({
                "index":i,"file":name,"slides":ids,"boundary_kind":"whole_slide",
                "expected_wav_seconds":round(seconds,4),
                "actual_seconds":checked["seconds"],"sha256":sha256(output),
            })
        receipt={
            "schema_version":1,"validation":"verified_slide_boundary_parts",
            "source_media_sha256":_keys(shadow,count),"parts":parts,
            "automatic":True,"human_approval_is_gate":False,
            "publication_allowed":False,
        }
        (shadow/PARTS_RECEIPT).write_text(
            json.dumps(receipt,indent=2),encoding="utf8")
        verify_parts(shadow)
        verified=visual_audit(shadow,ffmpeg=ffmpeg)
        if verified.get("cue_count",0)<1 or (
                len(verified.get("verified_delivery_parts",[]))!=len(parts)):
            raise TimedLongTransactionError("Incomplete independent part visual QA")
        if _input_inventory(stage,count,timed)!=snapshot:
            raise TimedLongTransactionError("Inputs changed during long candidate verification")
        if sha256(candidate)!=sha256(shadow/"slides.mp4"):
            raise TimedLongTransactionError("Full candidate mutated during QA")
        # Persist an exclusive, source-hash-bound recovery journal before
        # the first hard link. An abrupt process kill leaves this evidence
        # available for safe byte-specific cleanup or verification on resume.
        outputs=["slides.mp4",*piece_names,PARTS_RECEIPT,VISUAL_RECEIPT]
        journal=stage/JOURNAL
        with journal.open("x",encoding="utf8") as out:
            json.dump({
                "schema_version":1,"publication_allowed":False,
                "input_sha256":snapshot,
                "output_sha256":{name:sha256(shadow/name) for name in outputs},
            },out,indent=2)
            out.flush()
            os.fsync(out.fileno())
        installed=[]
        try:
            for name in outputs:
                destination=stage/name
                _link(shadow/name,destination)
                installed.append(destination)
            verify_parts(stage)
            verify_visual(stage,ffmpeg=ffmpeg)
            if _input_inventory(stage,count,timed)!=snapshot:
                raise TimedLongTransactionError("Inputs changed during final commit")
            journal.unlink()
        except Exception:
            for path in reversed(installed):
                path.unlink(missing_ok=True)
            journal.unlink(missing_ok=True)
            raise
        return {
            "status":"PRIVATE_SOURCE_PCM_TIMED_LONG_VIDEO_VERIFIED",
            "parts":len(parts),"slides":count,"cues":verified["cue_count"],
            "publication_allowed":False,
        }
