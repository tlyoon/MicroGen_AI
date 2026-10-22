"""Read-only short PCM audio witnesses from original lecture MP4.

Acoustic energy is not phonetic correctness, narrated-word alignment, or academic approval.
No paid services, no media modification and no automatic publication.
"""
from __future__ import annotations
import hashlib,json,math,re,struct,subprocess
from pathlib import Path
from microgen_tts_highlight_evidence import HighlightEvidenceError,validate_manifest,verify_cue_timing,_sha_file,audit_highlight_evidence

class AudioEvidenceError(ValueError):
    pass

SAMPLE_RATE=16000
MAX_MP4_BYTES=12*1024**3

def _finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def validate_audio_window(video, start, seconds, *, duration):
    path=Path(video)
    if path.suffix.lower()!=".mp4" or path.is_symlink() or not path.is_file():
        raise AudioEvidenceError("Existing regular MP4 required")
    size=path.stat().st_size
    if not 0 < size <= MAX_MP4_BYTES:
        raise AudioEvidenceError("Empty or oversized MP4")
    if not all(_finite(v) for v in (start,seconds,duration)):
        raise AudioEvidenceError("Finite audio interval required")
    if not (0 < duration < 600 and 0<=start and 0.05<=seconds<=1.0 and start+seconds<=duration+1e-8):
        raise AudioEvidenceError("Unsafe or out-of-bounds audio window")
    return {"source":str(path),"start_seconds":float(start),"window_seconds":float(seconds),
            "sample_rate":SAMPLE_RATE,"duration_seconds":float(duration)}
