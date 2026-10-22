"""Read-only, fail-closed evidence probes for element-level lecture highlights.

Never equate matching source hashes or visual pixels with true spoken phonemes,
mathematical validity, or publication authorization.
"""
from __future__ import annotations
import hashlib,io,json,math,re,subprocess
from pathlib import Path

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")

class HighlightEvidenceError(ValueError):
    pass

def _finite_number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "video_sha256", "cues"}:
        raise HighlightEvidenceError("Unexpected manifest structure")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise HighlightEvidenceError("Unsupported manifest version")
    if not isinstance(manifest["video_sha256"], str) or not _SHA256_RE.fullmatch(manifest["video_sha256"]):
        raise HighlightEvidenceError("Invalid video fingerprint")
    cues = manifest["cues"]
    if not isinstance(cues, list) or not (1 <= len(cues) <= 2048):
        raise HighlightEvidenceError("Cue list must have 1..2048 entries")
    ids = set()
    expected = {"cue_id", "slide_number", "element_id", "narration_id", "start_seconds", "end_seconds", "box", "slide_image_sha256"}
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != expected:
            raise HighlightEvidenceError("Unexpected cue fields")
        for key in ("cue_id", "element_id", "narration_id"):
            if not isinstance(cue[key], str) or not _IDENT_RE.fullmatch(cue[key]):
                raise HighlightEvidenceError("Invalid cue identity")
        if cue["cue_id"] in ids:
            raise HighlightEvidenceError("Duplicate cue identity")
        ids.add(cue["cue_id"])
        if type(cue["slide_number"]) is not int or cue["slide_number"] < 1:
            raise HighlightEvidenceError("Invalid slide number")
        if not isinstance(cue["slide_image_sha256"], str) or not _SHA256_RE.fullmatch(cue["slide_image_sha256"]):
            raise HighlightEvidenceError("Invalid slide fingerprint")
        start, end = cue["start_seconds"], cue["end_seconds"]
        if not _finite_number(start) or not _finite_number(end) or not (0 <= start < end):
            raise HighlightEvidenceError("Invalid cue interval")
        box = cue["box"]
        if not isinstance(box, list) or len(box) != 4 or any(type(x) is not int or x < 0 for x in box):
            raise HighlightEvidenceError("Invalid video pixel region")
        if not (box[0] < box[2] and box[1] < box[3]):
            raise HighlightEvidenceError("Empty cue pixel region")
    return {"status": "MANIFEST_SCHEMA_VALID", "cue_count": len(cues),
            "spoken_narration_verified": False, "highlight_sync_verified": False,
            "ready_for_publication": False}

def verify_cue_timing(manifest, duration_seconds):
    validate_manifest(manifest)
    if not _finite_number(duration_seconds) or not (0 < duration_seconds < 600):
        raise HighlightEvidenceError("Video must be strictly under 600 seconds")
    last_end = 0.0
    for cue in manifest["cues"]:
        if cue["start_seconds"] < last_end or cue["end_seconds"] > duration_seconds:
            raise HighlightEvidenceError("Overlapping, unordered or out-of-range cue")
        last_end = cue["end_seconds"]
    return {"temporal_contract_pass": True, "video_duration_seconds": duration_seconds,
            "narration_highlight_sync_verified": False}

def verify_narration_claims(manifest, segments):
    validate_manifest(manifest)
    if not isinstance(segments, list) or not (1 <= len(segments) <= 2048):
        raise HighlightEvidenceError("Explicit bounded narration segments required")
    by_id = {}; previous_end = 0.0
    for seg in segments:
        if not isinstance(seg, dict) or set(seg) != {"narration_id", "start_seconds", "end_seconds"}:
            raise HighlightEvidenceError("Malformed narration segment")
        ident, start, end = seg["narration_id"], seg["start_seconds"], seg["end_seconds"]
        if not isinstance(ident, str) or not _IDENT_RE.fullmatch(ident) or ident in by_id:
            raise HighlightEvidenceError("Duplicate or invalid narration segment identity")
        if not _finite_number(start) or not _finite_number(end) or not (previous_end <= start < end):
            raise HighlightEvidenceError("Narration segments out of order or overlapping")
        by_id[ident] = (start, end); previous_end = end
    used = set()
    for cue in manifest["cues"]:
        ident = cue["narration_id"]; used.add(ident)
        if ident not in by_id:
            raise HighlightEvidenceError("Highlight cue lacks narration segment")
        start, end = by_id[ident]
        if cue["start_seconds"] < start or cue["end_seconds"] > end:
            raise HighlightEvidenceError("Highlight interval exceeds claimed narration")
    if set(by_id) != used:
        raise HighlightEvidenceError("Unmapped narration segment")
    return {"claimed_narration_intervals_consistent": True,
            "actual_spoken_words_or_onsets_verified": False}

def _sha_file(path):
    digest=hashlib.sha256()
    with open(path,"rb") as stream:
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:break
            digest.update(chunk)
    return digest.hexdigest()

def verify_slide_sources(manifest, source_index):
    validate_manifest(manifest)
    if not isinstance(source_index, dict):
        raise HighlightEvidenceError("Explicit source index required")
    expected = {cue["slide_image_sha256"] for cue in manifest["cues"]}
    if set(source_index) != expected:
        raise HighlightEvidenceError("Source index is incomplete or contains extra entries")
    for fingerprint, filename in source_index.items():
        if not isinstance(filename, (str, Path)):
            raise HighlightEvidenceError("Invalid image source")
        path=Path(filename)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 80*1024*1024:
            raise HighlightEvidenceError("Unsafe or missing source image")
        before=path.stat();digest=_sha_file(path);after=path.stat()
        if digest!=fingerprint or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise HighlightEvidenceError("Slide source fingerprint mismatch or source mutation")
    return {"slide_sources_sha256_verified":True, "slide_semantics_verified":False}

def capture_frame(video_path, at_seconds, *, timeout=25):
    video=Path(video_path)
    if not _finite_number(at_seconds) or not (0 <= at_seconds < 600):
        raise HighlightEvidenceError("Unsafe frame sample time")
    if video.suffix.lower() != ".mp4" or video.is_symlink() or not video.is_file():
        raise HighlightEvidenceError("Explicit regular MP4 required")
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-ss",format(at_seconds,".6f"),"-i",str(video),
         "-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"]
    try:
        result=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=False,timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HighlightEvidenceError("FFmpeg sample failed") from exc
    if result.returncode != 0 or not result.stdout or len(result.stdout)>32*1024*1024:
        raise HighlightEvidenceError("Invalid FFmpeg PNG sample")
    return result.stdout

def measure_frame_change(before_png, after_png, box):
    from PIL import Image, UnidentifiedImageError
    # Pillow tolerates a missing PNG IEND chunk on some platforms/versions.
    # Independently refuse incomplete FFmpeg evidence frames on every OS.
    trailer = bytes.fromhex("0000000049454e44ae426082")
    if any(not isinstance(data, bytes) or not data.endswith(trailer)
           for data in (before_png, after_png)):
        raise HighlightEvidenceError("Incomplete PNG frame evidence: missing IEND")
    try:
        with Image.open(io.BytesIO(before_png)) as first, Image.open(io.BytesIO(after_png)) as second:
            if first.size != second.size or first.width*first.height > 16_000_000:
                raise HighlightEvidenceError("Frame dimensions mismatch or too large")
            image_a=first.convert("RGB");image_b=second.convert("RGB")
    except (OSError,ValueError,UnidentifiedImageError) as exc:
        raise HighlightEvidenceError("Frame PNG decode failed") from exc
    width,height=image_a.size
    if not isinstance(box,list) or len(box)!=4 or any(type(n) is not int for n in box):
        raise HighlightEvidenceError("Malformed target bounding box")
    left,top,right,bottom=box
    if not (0<=left<right<=width and 0<=top<bottom<=height):
        raise HighlightEvidenceError("Target region lies outside actual video frame")
    a=image_a.load();b=image_b.load()
    target_sum=outside_sum=target_pixels=outside_pixels=0
    for y in range(height):
        for x in range(width):
            delta=sum(abs(a[x,y][k]-b[x,y][k]) for k in range(3))/3
            if left<=x<right and top<=y<bottom:
                target_sum+=delta;target_pixels+=1
            else:
                outside_sum+=delta;outside_pixels+=1
    if outside_pixels==0:
        raise HighlightEvidenceError("Cannot distinguish full-frame change from highlight")
    return {"target_mean_rgb_delta":target_sum/target_pixels,
            "outside_mean_rgb_delta":outside_sum/outside_pixels,
            "target_pixel_count":target_pixels,
            "outside_pixel_count":outside_pixels}

def judge_localized_highlight(differences, *, min_target_delta=12.0, max_outside_delta=4.0):
    if not isinstance(differences, dict):
        raise HighlightEvidenceError("Pixel measurements required")
    target=differences.get("target_mean_rgb_delta");outside=differences.get("outside_mean_rgb_delta")
    if not _finite_number(target) or not _finite_number(outside) or target<0 or outside<0:
        raise HighlightEvidenceError("Invalid pixel evidence")
    if not _finite_number(min_target_delta) or not _finite_number(max_outside_delta) or not (0<min_target_delta<=255 and 0<=max_outside_delta<255):
        raise HighlightEvidenceError("Unsafe pixel thresholds")
    passed = target>=min_target_delta and outside<=max_outside_delta and target>=outside+8
    return {"localized_visual_change_pass":bool(passed),
            "visual_evidence_only":True,"speech_cue_alignment_certified":False}

def verify_cue_visual_witness(manifest, cue, video_path, duration_seconds, *, margin=0.08):
    validate_manifest(manifest)
    verify_cue_timing(manifest,duration_seconds)
    if cue not in manifest["cues"]:
        raise HighlightEvidenceError("Cue not bound to manifest")
    if not _finite_number(margin) or not (0<margin<=0.5):
        raise HighlightEvidenceError("Unsafe visual witness margin")
    start,end=cue["start_seconds"],cue["end_seconds"]
    if not (start>=margin and end-start>2*margin):
        raise HighlightEvidenceError("Cue lacks separate before and active witness windows")
    p=Path(video_path)
    before_sha=_sha_file(p)
    if before_sha != manifest["video_sha256"]:
        raise HighlightEvidenceError("Video SHA-256 does not match cue manifest")
    off=capture_frame(p,start-margin)
    on=capture_frame(p,start+margin)
    if _sha_file(p)!=before_sha:
        raise HighlightEvidenceError("MP4 changed during frame evidence sampling")
    difference=measure_frame_change(off,on,cue["box"])
    status=judge_localized_highlight(difference)
    return {"cue_id":cue["cue_id"], "video_sha256_verified":True,
            "before_second":start-margin,"active_second":start+margin,
            "pixel_evidence":difference,**status,
            "actual_narration_sync_certified":False}
