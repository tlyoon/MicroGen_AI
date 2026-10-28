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

def group_claimed_reviews(packet,*,min_claimed_reviewers=2):
    validate_review_packet(packet)
    if type(min_claimed_reviewers) is not int or not 2<=min_claimed_reviewers<=8:
        raise AnnotationError("Invalid minimum number of reviewers")
    groups={}
    for item in packet["observations"]:
        groups.setdefault(item["event_id"],[]).append(item)
    summaries={}
    for identifier,rows in groups.items():
        identifiers={e["reviewer_id"] for e in rows}
        enough=len(identifiers)>=min_claimed_reviewers
        summaries[identifier]={"claimed_reviewer_count":len(identifiers),
            "minimum_claims_met":enough,"identity_independence_authenticated":False,
            "status":"CLAIMED_REVIEWER_COUNT_MET" if enough else "INSUFFICIENT_CLAIMED_REVIEWERS"}
    return summaries

def summarize_review_agreement(packet):
    grouped=group_claimed_reviews(packet)
    observations={}
    for e in packet["observations"]:
        observations.setdefault(e["event_id"],[]).append(e)
    results={}
    for event_id,rows in observations.items():
        labels={r["verdict"] for r in rows}
        if not grouped[event_id]["minimum_claims_met"]:
            state="INSUFFICIENT_REVIEWER_CLAIMS"
        elif "UNCERTAIN" in labels:
            state="REVIEW_UNCERTAIN"
        elif len(labels)>1:
            state="REVIEWER_DISAGREEMENT"
        elif labels=={"DEFECT"}:
            state="REVIEWERS_REPORT_DEFECT"
        else:
            state="REVIEWERS_REPORT_CORRECT_UNVERIFIED"
        results[event_id]={**grouped[event_id],"status":state,
                           "heard_phrases":sorted({r["heard_phrase"] for r in rows}),
                           "phonetic_truth_verified":False,"ready_for_publication":False}
    return results

def verify_review_cue_bounds(packet,manifest,*,duration_seconds):
    validate_review_packet(packet)
    validate_manifest(manifest)
    verify_cue_timing(manifest,duration_seconds)
    if packet["video_sha256"]!=manifest["video_sha256"]:
        raise AnnotationError("Reviewer packet and cue manifest refer to different MP4s")
    cues={e["cue_id"]:e for e in manifest["cues"]}
    for event in packet["observations"]:
        cue=cues.get(event["cue_id"])
        if cue is None:
            raise AnnotationError("Review references unknown visual highlight cue")
        if not (cue["start_seconds"]<=event["start_seconds"] and
                event["start_seconds"]+event["window_seconds"]<=cue["end_seconds"]):
            raise AnnotationError("Review clip lies outside claimed visual cue interval")
    return {"clock_claims_compatible":True,"real_spoken_words_aligned_to_element":False}

def audit_pronunciation_packet(packet,manifest,video):
    shape=validate_review_packet(packet)
    if shape["event_count"]>32:
        raise AnnotationError("Too many distinct audio clips for one bounded audit")
    media=inspect_real_av_video(video)
    if media["video_sha256"]!=packet["video_sha256"]:
        raise AnnotationError("Real MP4 does not match observation packet checksum")
    verify_review_cue_bounds(packet,manifest,duration_seconds=media["duration_seconds"])
    witness_rows={}
    for item in packet["observations"]:
        if item["event_id"] not in witness_rows:
            witness_rows[item["event_id"]]=verify_label_clip(video,media["video_sha256"],item,
                duration_seconds=media["duration_seconds"])
    agreements=summarize_review_agreement(packet)
    defects=sorted(k for k,v in agreements.items() if v["status"]=="REVIEWERS_REPORT_DEFECT")
    uncertain=sorted(k for k,v in agreements.items() if v["status"] not in
         ("REVIEWERS_REPORT_DEFECT","REVIEWERS_REPORT_CORRECT_UNVERIFIED"))
    return {"schema_version":1,
       "status":"REVIEWERS_REPORTED_PRONUNCIATION_DEFECT" if defects else
                "ANNOTATIONS_INCOMPLETE_OR_DISPUTED" if uncertain else
                "UNAUTHENTICATED_REVIEWER_CORRECTNESS_CLAIMS",
       "media":media,"event_count":shape["event_count"],
       "source_bound_pcm_clip_count":len(witness_rows),
       "agreement":agreements,"defect_event_ids":defects,"unresolved_event_ids":uncertain,
       "actual_phonemes_verified":False,"reviewer_identity_authenticated":False,
       "narration_highlight_sync_verified":False,
       "ready_for_publication":False,"assets_modified":False,"publication_performed":False}

def _read_json(path):
    from microgen_tts_highlight_evidence import _read_json_strict
    return _read_json_strict(Path(path))

def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Read-only independent-review evidence diagnostics")
    parser.add_argument("--video",required=True,type=Path)
    parser.add_argument("--review-packet",type=Path)
    parser.add_argument("--highlight-manifest",type=Path)
    args=parser.parse_args(argv)
    try:
        if args.review_packet is None and args.highlight_manifest is None:
            media=inspect_real_av_video(args.video)
            result={"status":"REVIEW_PACKET_ABSENT","source_video":media,
                "blocking_reason":"Independent grounded labels and cue manifest not supplied"}
        elif args.review_packet is not None and args.highlight_manifest is not None:
            result=audit_pronunciation_packet(_read_json(args.review_packet),
                                               _read_json(args.highlight_manifest),args.video)
        else:
            raise AnnotationError("Both review packet and highlight manifest required")
    except (AnnotationError,AudioEvidenceError,HighlightEvidenceError,OSError,ValueError) as exc:
        result={"status":"REVIEW_AUDIT_BLOCKED","blocking_reason":str(exc)}
    result["ready_for_publication"]=False
    result["assets_modified"]=False
    result["publication_performed"]=False
    print(json.dumps(result,indent=2,sort_keys=True))
    return 2

if __name__=="__main__":
    raise SystemExit(main())
