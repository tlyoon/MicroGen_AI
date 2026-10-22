"""External pronunciation-review observations pinned to read-only real MP4 PCM.

Never infer independent reviewer identity, correct phonemes, or synchronized visual highlight
from audio energy or unverified declarative review labels. No publication.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re
from pathlib import Path
from microgen_tts_av_evidence import AudioEvidenceError,_finite,validate_audio_window,extract_pcm_window,pcm_energy,inspect_real_av_video
from microgen_tts_highlight_evidence import HighlightEvidenceError,_sha_file,validate_manifest,verify_cue_timing

class AnnotationError(ValueError):
    pass

_HASH=re.compile(r"[0-9a-f]{64}\Z")
_IDENT=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")

def witness_pcm(video, expected_sha256, start_seconds, window_seconds, *, duration_seconds):
    if not isinstance(expected_sha256,str) or not _HASH.fullmatch(expected_sha256):
        raise AnnotationError("Invalid original MP4 fingerprint")
    validate_audio_window(video,start_seconds,window_seconds,duration=duration_seconds)
    p=Path(video)
    before=_sha_file(p)
    if before!=expected_sha256:
        raise AnnotationError("Original MP4 checksum differs")
    data=extract_pcm_window(p,start_seconds,window_seconds,duration=duration_seconds)
    if _sha_file(p)!=before:
        raise AnnotationError("Source MP4 changed while sampling")
    measurements=pcm_energy(data)
    return {"video_sha256_verified":True,"video_sha256":before,
            "start_seconds":float(start_seconds),"window_seconds":float(window_seconds),
            "pcm_sha256":measurements["decoded_pcm_sha256"],
            "sample_count":measurements["sample_count"],
            "rms":measurements["rms"],
            "clipped_fraction":measurements["clipped_fraction"],
            "pronunciation_verified":False}

_EVENT_KEYS={"event_id","cue_id","expected_phrase","heard_phrase","verdict",
            "start_seconds","window_seconds","pcm_sha256","reviewer_id"}

def validate_event(observation):
    if not isinstance(observation,dict) or set(observation)!=_EVENT_KEYS:
        raise AnnotationError("Pronunciation observation does not match strict schema")
    for key in ("event_id","cue_id","reviewer_id"):
        if not isinstance(observation[key],str) or not _IDENT.fullmatch(observation[key]):
            raise AnnotationError("Invalid event or reviewer identifier")
    for key in ("expected_phrase","heard_phrase"):
        value=observation[key]
        if not isinstance(value,str) or not (1<=len(value)<=180) or value!=value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
            raise AnnotationError("Invalid expected/heard phrase")
    if observation["verdict"] not in ("CORRECT","DEFECT","UNCERTAIN"):
        raise AnnotationError("Review verdict must be explicit")
    if not isinstance(observation["pcm_sha256"],str) or not _HASH.fullmatch(observation["pcm_sha256"]):
        raise AnnotationError("Missing audio clip checksum")
    start=observation["start_seconds"];seconds=observation["window_seconds"]
    if not all(_finite(x) for x in (start,seconds)) or not (0<=start<600 and .05<=seconds<=1 and start+seconds<600):
        raise AnnotationError("Invalid bounded observation time")
    return {"schema_valid":True,"claimed_reviewer_only":True,"independent_acoustic_truth_verified":False}

def verify_label_clip(video,video_sha,event,*,duration_seconds):
    validate_event(event)
    witness=witness_pcm(video,video_sha,event["start_seconds"],event["window_seconds"],
                        duration_seconds=duration_seconds)
    if event["pcm_sha256"]!=witness["pcm_sha256"]:
        raise AnnotationError("Reviewer-referenced PCM clip checksum does not match actual MP4 audio")
    return {"event_id":event["event_id"],"reviewer_id":event["reviewer_id"],
            "waveform_source_verified":True,"acoustic_clip":witness,
            "reviewer_identity_authenticated":False,"phonetic_label_verified":False}

def validate_review_packet(packet):
    if not isinstance(packet,dict) or set(packet)!={"schema_version","video_sha256","observations"}:
        raise AnnotationError("Invalid review packet envelope")
    if type(packet["schema_version"]) is not int or packet["schema_version"]!=1:
        raise AnnotationError("Unsupported review schema")
    sha=packet["video_sha256"]
    if not isinstance(sha,str) or not _HASH.fullmatch(sha):
        raise AnnotationError("Review packet video checksum missing")
    items=packet["observations"]
    if not isinstance(items,list) or not 1<=len(items)<=128:
        raise AnnotationError("Review packet must have 1..128 observations")
    identity=set();event_sources={}
    for e in items:
        validate_event(e)
        key=(e["event_id"],e["reviewer_id"])
        if key in identity:
            raise AnnotationError("Duplicate reviewer observation")
        identity.add(key)
        common=(e["cue_id"],e["expected_phrase"],e["start_seconds"],e["window_seconds"],e["pcm_sha256"])
        prior=event_sources.setdefault(e["event_id"],common)
        if prior!=common:
            raise AnnotationError("Reviewers disagree on clip identity or source metadata")
    return {"event_count":len(event_sources),"observation_count":len(items),
            "packet_structurally_consistent":True,"independent_reviewers_verified":False}
