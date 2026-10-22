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

def extract_pcm_window(video,start,seconds,*,duration,timeout=25):
    validate_audio_window(video,start,seconds,duration=duration)
    if not _finite(timeout) or not 1<=timeout<=60:
        raise AudioEvidenceError("Invalid FFmpeg timeout")
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-ss",format(start,".6f"),"-i",str(video),"-t",format(seconds,".6f"),
         "-map","0:a:0","-vn","-ac","1","-ar",str(SAMPLE_RATE),
         "-c:a","pcm_s16le","-f","s16le","-fs","40000","pipe:1"]
    try:
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              check=False,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise AudioEvidenceError("Audio FFmpeg subprocess failed") from exc
    raw=result.stdout
    if result.returncode!=0 or not isinstance(raw,bytes) or not 800<=len(raw)<=34000 or len(raw)%2:
        raise AudioEvidenceError("No valid bounded mono PCM output")
    return raw

def pcm_energy(pcm):
    if not isinstance(pcm,bytes) or not 800<=len(pcm)<=34000 or len(pcm)%2:
        raise AudioEvidenceError("Invalid signed PCM16 evidence")
    n=len(pcm)//2
    squares=0; peak=0; clipped=0
    for (value,) in struct.iter_unpack("<h",pcm):
        absval=abs(value);squares+=value*value
        peak=max(peak,absval)
        if absval>=32700:clipped+=1
    return {"sample_count":n,"rms":math.sqrt(squares/n)/32768.0,
            "peak":peak/32768.0,"clipped_fraction":clipped/n,
            "decoded_pcm_sha256":hashlib.sha256(pcm).hexdigest(),
            "spoken_words_verified":False}

def classify_acoustic_activity(metrics,*,rms_floor=.018,clipping_limit=.10):
    if not isinstance(metrics,dict):
        raise AudioEvidenceError("PCM energy metrics required")
    rms=metrics.get("rms");peak=metrics.get("peak");clipped=metrics.get("clipped_fraction")
    if not all(_finite(x) and 0<=x<=1 for x in (rms,peak,clipped)):
        raise AudioEvidenceError("Nonfinite or invalid PCM energy metrics")
    if not _finite(rms_floor) or not _finite(clipping_limit) or not (0<rms_floor<1 and 0<=clipping_limit<1):
        raise AudioEvidenceError("Invalid activity thresholds")
    if clipped>clipping_limit:
        label="UNRELIABLE_CLIPPED_AUDIO"
    elif rms<rms_floor:
        label="BELOW_SPEECH_LIKE_ENERGY_THRESHOLD"
    else:
        label="ACOUSTIC_ENERGY_PRESENT"
    return {"activity_label":label,"acoustic_energy_present":label=="ACOUSTIC_ENERGY_PRESENT",
            "speech_or_phonetic_identity_verified":False}

def probe_audio_cue(video,cue,*,duration):
    if not isinstance(cue,dict) or not {"cue_id","start_seconds","end_seconds"}<=set(cue):
        raise AudioEvidenceError("Cue identity and interval required")
    start,end=cue["start_seconds"],cue["end_seconds"]
    if not _finite(start) or not _finite(end) or not (0<=start<end<=duration):
        raise AudioEvidenceError("Malformed audio cue interval")
    span=end-start
    if span < .30:
        return {"cue_id":cue["cue_id"],"status":"ABSTAIN_CUE_TOO_SHORT",
                "samples":[],"energy_evidence_pass":False,"spoken_words_verified":False}
    window=min(.16,span/5)
    marks=(start+span*.18,start+span*.62)
    rows=[]
    for at in marks:
        raw=extract_pcm_window(video,at,window,duration=duration)
        stats=pcm_energy(raw)
        rows.append({"start_seconds":at,"window_seconds":window,
                     "metrics":stats,"activity":classify_acoustic_activity(stats)})
    passed=all(x["activity"]["acoustic_energy_present"] for x in rows)
    return {"cue_id":cue["cue_id"],"status":"ACOUSTIC_ENERGY_IN_TWO_WINDOWS" if passed else "INSUFFICIENT_CUE_ACOUSTIC_ACTIVITY",
            "samples":rows,"energy_evidence_pass":passed,
            "spoken_words_verified":False}

def fingerprint_bound_audio_cue(video,expected_sha,cue,*,duration):
    if not isinstance(expected_sha,str) or re.fullmatch(r"[0-9a-f]{64}",expected_sha) is None:
        raise AudioEvidenceError("Invalid expected MP4 fingerprint")
    path=Path(video)
    if path.is_symlink() or not path.is_file():
        raise AudioEvidenceError("Unsafe or missing video")
    before=_sha_file(path)
    if before!=expected_sha:
        raise AudioEvidenceError("MP4 mismatches its declared source SHA-256")
    result=probe_audio_cue(path,cue,duration=duration)
    if _sha_file(path)!=before:
        raise AudioEvidenceError("MP4 changed during acoustic witness")
    return {"video_sha256_verified":True,**result}

def inspect_real_av_video(video):
    from microgen_quality import check_video,QualityError
    path=Path(video)
    if path.is_symlink() or not path.is_file() or path.suffix.lower()!=".mp4":
        raise AudioEvidenceError("Existing regular MP4 required")
    try:
        details=check_video(path)
        seconds=float(details["seconds"])
    except (OSError,ValueError,RuntimeError,QualityError,KeyError,TypeError) as exc:
        raise AudioEvidenceError("Real MP4 audio/video stream validation failed") from exc
    if not _finite(seconds) or not 0<seconds<600:
        raise AudioEvidenceError("MP4 violates strict sub-600-second contract")
    return {"duration_seconds":seconds,"real_av_streams_checked":True,
            "video_sha256":_sha_file(path),"phoneme_accuracy_verified":False,
            "narration_highlight_sync_verified":False,"ready_for_publication":False}

def audit_audio_manifest(manifest,video):
    validate_manifest(manifest)
    if len(manifest["cues"])>32:
        raise AudioEvidenceError("At most 32 cues allowed in one bounded audit")
    info=inspect_real_av_video(video)
    if info["video_sha256"]!=manifest["video_sha256"]:
        raise AudioEvidenceError("Manifest bound to different MP4")
    verify_cue_timing(manifest,info["duration_seconds"])
    rows=[fingerprint_bound_audio_cue(video,manifest["video_sha256"],cue,
                                     duration=info["duration_seconds"])
          for cue in manifest["cues"]]
    passed=all(row["energy_evidence_pass"] for row in rows)
    return {"schema_version":1,
            "status":"ACOUSTIC_ENERGY_SUBSET_VERIFIED" if passed else "ACOUSTIC_EVIDENCE_BLOCKED",
            "video":info,"cues":rows,"all_cues_energy_present":passed,
            "actual_spoken_words_verified":False,
            "actual_narration_highlight_sync_verified":False,
            "ready_for_publication":False,"assets_modified":False}

def audit_multimodal_claims(manifest,segments,source_index,video):
    visual=audit_highlight_evidence(manifest,segments,source_index,video)
    acoustic=audit_audio_manifest(manifest,video)
    technical=bool(visual["all_cues_visual_evidence_pass"] and acoustic["all_cues_energy_present"])
    return {"schema_version":1,
            "status":"MULTIMODAL_TECHNICAL_SUBSET_VERIFIED" if technical else "MULTIMODAL_EVIDENCE_BLOCKED",
            "visual":visual,"acoustic":acoustic,
            "visual_and_acoustic_activity_pass":technical,
            "independently_verified_word_level_alignment":False,
            "phoneme_accuracy_verified":False,
            "figure_or_mathematical_accuracy_verified":False,
            "ready_for_publication":False,"assets_modified":False,"publication_performed":False}
