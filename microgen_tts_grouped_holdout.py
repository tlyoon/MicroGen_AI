"""Leakage-aware grouped partitions. Metadata labels are NOT trusted truth."""
from __future__ import annotations
import hashlib,re

class HoldoutError(ValueError):pass
SHA=re.compile(r"^[a-f0-9]{64}$")
def partition_corpus(records:list[dict],*,max_items:int=5000,
                     min_source_groups:int=6)->dict:
    if (not isinstance(records,list) or not records or
        type(max_items)!=int or not 1<=max_items<=10000 or len(records)>max_items):
        raise HoldoutError("Missing or unbounded acoustic corpus")
    if type(min_source_groups) is not int or not 3<=min_source_groups<=100:
        raise HoldoutError("Invalid minimum independent group threshold")
    groups={};seen_clips=set();sources={};pcm_sources={};pcm_count=0
    clip_pcm_sources={};clip_pcm_count=0
    for row in records:
        if not isinstance(row,dict):raise HoldoutError("Malformed sample row")
        source=row.get("source_wav_sha256");clip=row.get("clip_sha256")
        group=row.get("source_group_id");label=row.get("phoneme_label")
        if (not isinstance(source,str) or not SHA.fullmatch(source) or
            not isinstance(clip,str) or not SHA.fullmatch(clip) or
            not isinstance(group,str) or not 1<=len(group.strip())<=120 or
            label not in (None,"WHY","YAY")):
            raise HoldoutError("Invalid group/clip hash or phonetic label")
        if clip in seen_clips:raise HoldoutError("Duplicate clip in dataset")
        seen_clips.add(clip)
        if source in sources and sources[source]!=group:
            raise HoldoutError("Same source WAV assigned to different groups")
        pcm=row.get("source_pcm_sha256")
        if pcm is not None:
            if not isinstance(pcm,str) or not SHA.fullmatch(pcm):
                raise HoldoutError("Invalid decoded PCM fingerprint")
            if pcm in pcm_sources and pcm_sources[pcm]!=group:
                raise HoldoutError("Identical decoded PCM in different groups")
            pcm_sources[pcm]=group;pcm_count+=1
        clip_pcm=row.get("clip_pcm_sha256")
        if clip_pcm is not None:
            if not isinstance(clip_pcm,str) or not SHA.fullmatch(clip_pcm):
                raise HoldoutError("Invalid decoded clip PCM fingerprint")
            if clip_pcm in clip_pcm_sources and clip_pcm_sources[clip_pcm]!=group:
                raise HoldoutError("Identical decoded clip PCM in different groups")
            clip_pcm_sources[clip_pcm]=group;clip_pcm_count+=1
        sources[source]=group;groups.setdefault(group,[]).append(row)
    ordered=sorted(groups,key=lambda x:hashlib.sha256(x.encode("utf8")).hexdigest())
    partitions={"train":[],"holdout":[]}
    for i,group in enumerate(ordered):
        partitions["holdout" if i%3==0 else "train"].extend(groups[group])
    if len(ordered)==2:
        partitions={"holdout":list(groups[ordered[0]]),"train":list(groups[ordered[1]])}
    train_sha={x["source_wav_sha256"] for x in partitions["train"]}
    eval_sha={x["source_wav_sha256"] for x in partitions["holdout"]}
    if train_sha&eval_sha:
        raise HoldoutError("Source SHA contamination between train and holdout")
    nonleaky=bool(partitions["train"] and partitions["holdout"])
    missing_labels=sum(x["phoneme_label"] is None for x in records)
    return {
        "schema_version":1,"total_clips":len(records),"distinct_source_groups":len(groups),
        "train_clip_sha256":[x["clip_sha256"] for x in partitions["train"]],
        "holdout_clip_sha256":[x["clip_sha256"] for x in partitions["holdout"]],
        "source_sha_overlap":sorted(train_sha&eval_sha),
        "source_pcm_identity_verified":pcm_count==len(records),
        "clip_pcm_identity_verified":clip_pcm_count==len(records),
        "grouped_holdout_available":nonleaky,
        "minimum_group_count_requested":min_source_groups,
        "minimum_group_count_met":len(groups)>=min_source_groups,
        "unlabelled_clips":missing_labels,
        "scoring_allowed":False,
        "scoring_blockers":(
            ["INSUFFICIENT_DISTINCT_SOURCE_GROUPS"] if not nonleaky else []
        )+(
            ["TOO_FEW_GROUPS_FOR_ROBUST_EVALUATION"] if len(groups)<min_source_groups else []
        )+(
            ["SOURCE_PCM_FINGERPRINTS_MISSING"] if pcm_count<len(records) else []
        )+(
            ["CLIP_PCM_FINGERPRINTS_MISSING"] if clip_pcm_count<len(records) else []
        )+(
            ["UNLABELLED_CLIPS_PRESENT"] if missing_labels else
            ["PHONEME_LABEL_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED"]
        ),
        "source_group_independence_independently_verified":False,
        "audio_qualification_passed":False,"manual_gate_required":False,
        "note":"Grouping is claimed metadata; no phoneme labels automatically certified",
    }
