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
