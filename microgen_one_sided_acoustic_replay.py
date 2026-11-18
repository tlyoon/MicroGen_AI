"""SHA-bound prior two-Gemini failed-ASR replay with finite one-model retakes.

For new authorized HP original API private campaigns only. Reuses the exact
previously paid blind transcripts for ALL WAVs, strictly recalculates their
source discrepancy, then permits ONE paid retake of each dissenting source-
sensitive model (max 2 slides), never another whole-deck 42-call review.
No old verdict or audio TTS approval is reused. Crash reservation is
persisted before every provider send; uncertain sends never repeat.
Only fresh source-matching retakes may yield a video-eligible acoustic gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
from datetime import datetime,timezone

from microgen_verified_acoustic_replay import (
    valid_trace, read_json, sha, OWNER,
)
from microgen_one_sided_acoustic_recheck import (
    source_exact_vs_one_sensitive,
)

RECEIPT=".microgen_one_sided_private_recheck.json"
MAX_RECHECK_SLIDES=2


class OneSidedAcousticReplayError(RuntimeError):
    pass


def _fsync_json(path:Path,value:dict,*,exclusive=False)->None:
    path=Path(path)
    if exclusive:
        with path.open("x",encoding="utf8") as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        return
    import tempfile
    handle,name=tempfile.mkstemp(
        prefix=".microgen-recheck-",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(handle,"w",encoding="utf8") as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def find_source_identical_failed_review(stage:Path,texts:list[str]):
    """Read-only matcher: one historical failed trace, not accepted claims."""
    from microgen_tts_acoustic_qa import _input_snapshot
    from microgen_autonomous_acoustic_gate import _normalized

    stage=Path(stage).resolve()
    root=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/"MicroGen_AI_Checkpoints"
    if (os.name!="nt" or socket.gethostname().casefold()!="hp"
            or stage.parent.parent!=root or not stage.is_dir()
            or not isinstance(texts,list) or not texts
            or texts!=_normalized(stage)):
        return None
    owner=read_json(stage.parent/OWNER)
    cp=read_json(stage/".microgen_checkpoint.json")
    if (owner is None or cp is None or
            owner.get("publication_authorized") is not False
            or owner.get("scope",{}).get("host")!="hp"
            or owner.get("scope",{}).get("work_root")!=str(stage.parent)
            or owner.get("scope",{}).get("stop_after")!="acceptance"
            or owner.get("scope",{}).get("source_sha256")!=sha(stage/"source.pdf")
            or cp.get("package_commit")!=owner.get("scope",{}).get("code_revision")
            or not cp.get("completed",{}).get("tts")):
        return None
    current=_input_snapshot(stage,len(texts))
    matches=[]
    for campaign in root.iterdir():
        if campaign==stage.parent or campaign.is_symlink() or not campaign.is_dir():
            continue
        old=campaign/stage.name
        grant=read_json(campaign/OWNER)
        old_cp=read_json(old/".microgen_checkpoint.json")
        if (grant is None or old_cp is None or not old.is_dir()
                or old.is_symlink()
                or grant.get("publication_authorized") is not False
                or grant.get("scope",{}).get("host")!="hp"
                or grant.get("scope",{}).get("work_root")!=str(campaign)
                or grant.get("scope",{}).get("stop_after")!="acceptance"
                or not (old/"source.pdf").is_file()
                or (old/"source.pdf").is_symlink()
                or sha(old/"source.pdf")!=sha(stage/"source.pdf")
                or grant.get("scope",{}).get("source_sha256")!=sha(stage/"source.pdf")
                or old_cp.get("package_commit")!=grant.get("scope",{}).get("code_revision")
                or not old_cp.get("completed",{}).get("tts")
                or not (old/"microgen_autonomous_acoustic_gate.py").is_file()
                or sha(old/"microgen_autonomous_acoustic_gate.py")
                   ==sha(stage/"microgen_autonomous_acoustic_gate.py")):
            continue
        for diagnostic_path in old.glob(".microgen_acoustic_blocked_*.json"):
            diagnostic=read_json(diagnostic_path,128_000)
            if (diagnostic is None or
                    diagnostic.get("status")!="INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED" or
                    diagnostic.get("root_cause_family")!="BOUNDED_SAME_VOICE_REPAIR_ELIGIBLE" or
                    diagnostic.get("input_snapshot_sha256")!=current or
                    diagnostic.get("private_blind_transcripts_retained") is not True or
                    diagnostic.get("safe_auto_repair") is not True):
                continue
            models=diagnostic.get("recognition_models")
            flagged=diagnostic.get("review_required_slides")
            if (not isinstance(models,list) or len(models)!=2
                    or models[0]==models[1]
                    or not all(isinstance(m,str) and m.startswith("gemini-") for m in models)
                    or not isinstance(flagged,list)
                    or not 1<=len(flagged)<=MAX_RECHECK_SLIDES):
                continue
            for path in old.glob(".microgen_private_acoustic_failed_*.json"):
                trace=valid_trace(path,current,len(texts),tuple(models))
                if trace is None or trace["review_required_slides"]!=flagged:
                    continue
                checked=[]
                for n in flagged:
                    row=trace["slides"][n-1]
                    if row.get("expected_spoken_sha256")!=hashlib.sha256(
                            texts[n-1].encode("utf8")).hexdigest():
                        checked=[]
                        break
                    original=row.get("original_blind_transcripts",[])
                    index=(source_exact_vs_one_sensitive(texts[n-1],*original)
                           if len(original)==2 else None)
                    if index is None:
                        checked=[]
                        break
                    checked.append((n,index))
                if len(checked)!=len(flagged):
                    continue
                if any(
                        row.get("expected_spoken_sha256")!=hashlib.sha256(
                            text.encode("utf8")).hexdigest()
                        for row,text in zip(trace["slides"],texts)
                ):
                    continue
                matches.append(
                    (diagnostic.get("audit_utc",""),old,path,trace,checked))
    if not matches:
        return None
    matches.sort(key=lambda item:item[0],reverse=True)
    if len(matches)>1 and matches[0][0]==matches[1][0]:
        raise OneSidedAcousticReplayError(
            "AMBIGUOUS_PRIOR_ONE_SIDED_ASR_HOLD")
    _,old,path,trace,checked=matches[0]
    return {"old":old,"trace_path":path,"trace":trace,
            "retakes":checked,"models":tuple(trace["models"])}


def replay_with_one_sided_rechecks(stage:Path,texts:list[str],
                                   *,provider_factory=None):
    """Return verified report/evidence or None; never automatically rerun a send."""
    from microgen_tts_acoustic_qa import audit_with_recognizer,mismatch_details
    from microgen_autonomous_acoustic_gate import _verify,_providers
    stage=Path(stage)
    found=find_source_identical_failed_review(stage,texts)
    if found is None:
        return None
    trace=found["trace"]
    original=[row["original_blind_transcripts"] for row in trace["slides"]]
    models=found["models"]
    receipt_path=stage/RECEIPT
    source_binding={
        "source_sha256":sha(stage/"source.pdf"),
        "input_snapshot_sha256":trace["source_snapshot_sha256"],
        "original_private_trace_sha256":sha(found["trace_path"]),
        "old_campaign":found["old"].parent.name,
        "models":list(models),
        "retake_slides":[{"slide":n,"reviewer_index":i}
                         for n,i in found["retakes"]],
    }
    existing=read_json(receipt_path,128_000) if receipt_path.exists() else None
    if receipt_path.exists() and existing is None:
        raise OneSidedAcousticReplayError("UNVERIFIABLE_RETAKE_RESERVATION_HOLD")
    if existing is not None:
        if (existing.get("schema_version")!=1 or
                existing.get("publication_allowed") is not False or
                existing.get("source_binding")!=source_binding or
                not isinstance(existing.get("attempts"),list)
                or len(existing["attempts"])!=len(found["retakes"])):
            raise OneSidedAcousticReplayError("RETAKE_RESERVATION_IDENTITY_HOLD")
    else:
        existing={
            "schema_version":1,
            "publication_allowed":False,
            "status":"FINITE_ASR_RETAKE_STARTED",
            "source_binding":source_binding,
            "attempts":[{
                "slide":n,"reviewer_index":i,
                "status":"NOT_SENT","transcript":None,
            } for n,i in found["retakes"]],
        }
        _fsync_json(receipt_path,existing,exclusive=True)

    if any(a["status"]=="RESERVED" for a in existing["attempts"]):
        raise OneSidedAcousticReplayError(
            "UNCERTAIN_PAID_ONE_SIDED_ASR_HOLD: cannot replay send")
    if any(a["status"]=="REJECTED" for a in existing["attempts"]):
        raise OneSidedAcousticReplayError(
            "ONE_SIDED_SENSITIVE_MATHEMATICS_HOLD: retake contradicted source")

    def report_from(retakes):
        def recognizer(index):
            def run(path):
                n=int(path.stem.removeprefix("slide"))
                if path!=stage/f"slide{n}.wav" or not 1<=n<=len(original):
                    raise OneSidedAcousticReplayError("Wrong source WAV in replay")
                return retakes.get((n,index),original[n-1][index])
            return run
        return audit_with_recognizer(
            stage,texts,recognizer(0),lambda x:x,
            independent_recognizer=recognizer(1),recognition_models=models)

    # Recalculate original old words under current code before ANY send.
    original_report=report_from({})
    if original_report["review_required_slides"]!=[
            item["slide"] for item in source_binding["retake_slides"]]:
        raise OneSidedAcousticReplayError(
            "Historical source/WAV ASR classification changed; no retake")

    to_retry=[a for a in existing["attempts"] if a["status"]=="NOT_SENT"]
    if to_retry:
        # In this historical-recheck path, an individual retake must not
        # fan out to multiple Gemini key slots or a replacement model.
        first,second,names=(provider_factory() if provider_factory is not None
                            else _providers(single_slot_only=True))
        if tuple(names)!=models:
            raise OneSidedAcousticReplayError(
                "Paid reviewer identity changed; no retake permitted")
        providers=(first,second)
    else:
        providers=None
    for a in to_retry:
        n,index=a["slide"],a["reviewer_index"]
        a["status"]="RESERVED"
        _fsync_json(receipt_path,existing)
        try:
            text=str(providers[index](stage/f"slide{n}.wav")).strip()
            if not 5<=len(text)<=12000:
                raise OneSidedAcousticReplayError("Unusable independent retake")
        except Exception as exc:
            # Keep the reserved effect in an uncertain state: no new send.
            raise OneSidedAcousticReplayError(
                "UNCERTAIN_PAID_ONE_SIDED_ASR_HOLD: no trusted reply") from exc
        a["transcript"]=text
        reference=original[n-1][1-index]
        d=mismatch_details(texts[n-1],text)
        agreement=mismatch_details(reference,text)
        accepted=(d["sensitive_mismatches"]==0 and
                  d["circa_red_flags"]==0 and
                  d["letter_y_yay_red_flags"]==0 and
                  d["difference_fraction_upper_bound"]<=0.02 and
                  agreement["sensitive_mismatches"]==0 and
                  agreement["difference_fraction_upper_bound"]<=0.02)
        a["status"]="SOURCE_CONFIRMED" if accepted else "REJECTED"
        _fsync_json(receipt_path,existing)
        if not accepted:
            raise OneSidedAcousticReplayError(
                "ONE_SIDED_SENSITIVE_MATHEMATICS_HOLD: contrary retake preserved")

    rechecks={
        (a["slide"],a["reviewer_index"]):a["transcript"]
        for a in existing["attempts"]
    }
    if len(rechecks)!=len(found["retakes"]) or any(
            a["status"]!="SOURCE_CONFIRMED" for a in existing["attempts"]):
        raise OneSidedAcousticReplayError("Missing strict retake evidence")
    report=report_from(rechecks)
    report["independent_one_sided_sensitive_rechecks"]={
        "attempted_slides":[n for n,_ in found["retakes"]],
        "resolved_slides":[n for n,_ in found["retakes"]],
        "historical_two_model_transcripts_reused":True,
        "publication_allowed":False,
    }
    _verify(stage,report,texts)
    existing["status"]="SOURCE_BOUND_RECHECKS_CONFIRMED"
    _fsync_json(receipt_path,existing)
    return {
        "report":report,
        "evidence":{
            "method":"SHA_BOUND_FAILED_TWO_GEMINI_PLUS_ONE_SIDED_RETAKES",
            "old_campaign":found["old"].parent.name,
            "original_private_trace_sha256":sha(found["trace_path"]),
            "private_retake_receipt_sha256":sha(receipt_path),
            "retake_count":len(found["retakes"]),
            "publication_allowed":False,
        }
    }


def verify_one_sided_replay(stage:Path,receipt:dict)->None:
    """Independent immutable downstream check; never calls Gemini."""
    from microgen_autonomous_acoustic_gate import _normalized
    from microgen_tts_acoustic_qa import _input_snapshot,mismatch_details
    stage=Path(stage)
    evidence=receipt.get("verified_one_sided_historical_asr")
    if evidence is None:
        return
    if (not isinstance(evidence,dict) or
            set(evidence)!={"method","old_campaign",
                          "original_private_trace_sha256",
                          "private_retake_receipt_sha256",
                          "retake_count","publication_allowed"} or
            evidence["method"]!="SHA_BOUND_FAILED_TWO_GEMINI_PLUS_ONE_SIDED_RETAKES" or
            evidence["publication_allowed"] is not False or
            type(evidence["retake_count"]) is not int or
            not 1<=evidence["retake_count"]<=MAX_RECHECK_SLIDES or
            receipt.get("repaired_audio_slides")!=0):
        raise OneSidedAcousticReplayError("Invalid historical retake receipt")
    path=stage/RECEIPT
    if not path.is_file() or path.is_symlink() or sha(path)!=evidence["private_retake_receipt_sha256"]:
        raise OneSidedAcousticReplayError("Private retake data changed")
    record=read_json(path,128_000)
    if (record is None or record.get("schema_version")!=1
            or record.get("status")!="SOURCE_BOUND_RECHECKS_CONFIRMED"
            or record.get("publication_allowed") is not False or
            record.get("source_binding",{}).get("input_snapshot_sha256")
              !=_input_snapshot(stage,receipt["slide_count"])
            or record.get("source_binding",{}).get("source_sha256")
              !=sha(stage/"source.pdf")
            or record.get("source_binding",{}).get("old_campaign")
              !=evidence["old_campaign"]
            or record.get("source_binding",{}).get("original_private_trace_sha256")
              !=evidence["original_private_trace_sha256"]):
        raise OneSidedAcousticReplayError("Invalid bound private retake record")
    found=find_source_identical_failed_review(stage,_normalized(stage))
    if (found is None or sha(found["trace_path"])!=
            evidence["original_private_trace_sha256"] or
            found["old"].parent.name!=evidence["old_campaign"] or
            tuple(receipt["recognition_models"])!=found["models"] or
            len(found["retakes"])!=evidence["retake_count"]):
        raise OneSidedAcousticReplayError("Authentic original Gemini trace missing")
    original=[r["original_blind_transcripts"] for r in found["trace"]["slides"]]
    expected=_normalized(stage)
    rows=receipt["independent_report"]["slides"]
    if len(rows)!=len(expected) or len(record.get("attempts",[]))!=len(found["retakes"]):
        raise OneSidedAcousticReplayError("Incomplete retake transcript inventory")
    replacements={}
    for a,(n,index) in zip(record["attempts"],found["retakes"]):
        if (a.get("slide")!=n or a.get("reviewer_index")!=index or
                a.get("status")!="SOURCE_CONFIRMED" or
                not isinstance(a.get("transcript"),str) or
                not 5<=len(a["transcript"])<=12000):
            raise OneSidedAcousticReplayError("Unverified retake claimant")
        d=mismatch_details(expected[n-1],a["transcript"])
        if (d["sensitive_mismatches"] or d["circa_red_flags"] or
                d["letter_y_yay_red_flags"] or
                d["difference_fraction_upper_bound"]>0.02):
            raise OneSidedAcousticReplayError("Retake changed math or source")
        replacements[(n,index)]=a["transcript"]
    for n,row in enumerate(rows,1):
        transcripts=[
            replacements.get((n,i),original[n-1][i]) for i in (0,1)]
        if row["transcripts"]!=transcripts:
            raise OneSidedAcousticReplayError("Source-blind transcript changed after QA")
