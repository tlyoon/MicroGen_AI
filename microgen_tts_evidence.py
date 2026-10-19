"""Strict acoustic evidence cross-check for MicroGen release readiness.

A model response is *not* a signed independent review. Reject forged,
incomplete or stale transcript claims before using them for a technical
screening pass. Human listening and publisher-controlled reviewer
authentication remain separately required.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from microgen_tts_acoustic_qa import mismatch_details

def sha(text:str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def verify_acoustic_evidence(report:dict|None, stage:Path, spoken:list[str],
                             wav_hashes:list[str], voice_manifest_hash:str) -> tuple[bool,list[str]]:
    problems=[]
    if not isinstance(report,dict):
        return False,["acoustic_receipt_missing"]
    if report.get("schema_version")!=1:
        problems.append("acoustic_schema_invalid")
    if report.get("slide_count")!=len(wav_hashes) or len(spoken)!=len(wav_hashes):
        problems.append("slide_count_mismatch")
    if report.get("voice_provenance_sha256")!=voice_manifest_hash:
        problems.append("voice_provenance_hash_mismatch")
    models=report.get("recognition_models")
    if not isinstance(models,list) or len(models)!=2 or any(
        not isinstance(x,str) or not x.strip() for x in models
    ) or (isinstance(models,list) and len(models)==2 and models[0]==models[1]):
        problems.append("acoustic_independence_unverified")
    if report.get("unavailable_recognizer_passes"):
        problems.append("acoustic_provider_unavailable")
    rows=report.get("slides")
    if not isinstance(rows,list) or len(rows)!=len(spoken):
        return False,problems+["incomplete_acoustic_rows"]
    claimed_review=report.get("review_required_slides")
    if not isinstance(claimed_review,list):
        problems.append("missing_review_summary")
        claimed_review=[]
    derived_review=[]
    for number,(row,input_text,wav_hash) in enumerate(zip(rows,spoken,wav_hashes),1):
        if not isinstance(row,dict):
            problems.append(f"invalid_row_{number}")
            continue
        status=row.get("assessment")
        if row.get("slide")!=number:
            problems.append(f"slide_id_{number}")
        if row.get("audio_sha256")!=wav_hash:
            problems.append(f"audio_drift_{number}")
        if row.get("expected_spoken_sha256")!=sha(input_text):
            problems.append(f"spoken_input_drift_{number}")
        transcripts=row.get("transcripts")
        comparisons=row.get("comparisons")
        if not isinstance(transcripts,list) or len(transcripts)!=2 or any(
            not isinstance(x,str) or len(x.strip())<5 for x in transcripts
        ):
            problems.append(f"transcripts_missing_{number}")
        if not isinstance(comparisons,list) or len(comparisons)!=2 or any(
            not isinstance(x,dict) for x in comparisons
        ):
            problems.append(f"comparisons_missing_{number}")
        else:
            if isinstance(transcripts,list) and len(transcripts)==2 and all(
                isinstance(x,str) and len(x.strip())>=5 for x in transcripts
            ):
                try:
                    recalculated=[mismatch_details(input_text,t) for t in transcripts]
                    for i,(declared,actual) in enumerate(zip(comparisons,recalculated),1):
                        for field in ("difference_fraction_upper_bound",
                                      "sensitive_mismatches","circa_red_flags",
                                      "letter_y_yay_red_flags"):
                            if declared.get(field)!=actual[field]:
                                problems.append(f"comparison_claim_drift_{number}_{i}_{field}")
                    if any(x["difference_fraction_upper_bound"]>0.05 or
                        x["sensitive_mismatches"] or x["circa_red_flags"] or
                        x["letter_y_yay_red_flags"] for x in recalculated):
                        problems.append(f"unresolved_mismatch_{number}")
                    disagreement=mismatch_details(transcripts[0],transcripts[1])
                    if disagreement["difference_fraction_upper_bound"]>0.05:
                        problems.append(f"independent_recognizers_disagree_{number}")
                except (ValueError,TypeError,KeyError):
                    problems.append(f"cannot_recalculate_transcripts_{number}")
        if status not in ("ASR_SCREEN_PASS_LISTENING_REQUIRED",
                          "REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK"):
            problems.append(f"unresolved_acoustic_status_{number}")
        if status != "ASR_SCREEN_PASS_LISTENING_REQUIRED":
            derived_review.append(number)
        if status=="REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK" and not row.get("source_pronunciation_risks"):
            problems.append(f"missing_source_risk_{number}")
        if status=="ASR_SCREEN_PASS_LISTENING_REQUIRED" and row.get("source_pronunciation_risks"):
            problems.append(f"uncleared_source_risk_{number}")
    if claimed_review!=derived_review:
        problems.append("acoustic_summary_inconsistent")
    if report.get("publishable") is True or report.get("human_listening_approved") is True:
        problems.append("acoustic_screen_must_not_assert_approval")
    return len(problems)==0,problems
