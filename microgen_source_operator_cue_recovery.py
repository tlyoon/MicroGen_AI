"""Single-source-math-operator, source/PCM-bound recovery (HP original API).

This repair uses genuine archived failed two-Gemini reviews and a prior
contrary retake to select one source-defined cue, then makes at most:
  ONE Gemini same-voice cue TTS and TWO source-blind whole-slide ASR calls.
Every billable send is reserved and fsynced before dispatch. Crash/uncertain
sends never replay. Never silently accept missing math or mutate old media.
Actual candidate must pass BOTH independent recognizers and full measured PCM.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile

JOURNAL=".microgen_source_operator_cue_repair.json"
ALLOWED_PROVIDER={"gemini_flash_lite_tts":"gemini-3.8-flash-lite-tts",
                  "gemini_flash_tts":"gemini-3.8-flash-tts"}


class SourceOperatorCueRecoveryError(RuntimeError):
    pass


def _sha(path:Path)->str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(stage:Path,state:dict,exclusive:bool=False)->None:
    from microgen_one_sided_acoustic_replay import _fsync_json
    _fsync_json(stage/JOURNAL,state,exclusive=exclusive)


def _eligible(stage:Path,texts:list[str]):
    from microgen_verified_acoustic_replay import sha,read_json,OWNER
    from microgen_one_sided_acoustic_replay import (
        find_source_identical_failed_review,RECEIPT,
    )
    from microgen_tts_acoustic_qa import audit_with_recognizer
    from microgen_source_bound_cue_selection import (
        choose_material_operator_cues,
    )
    stage=Path(stage).resolve()
    found=find_source_identical_failed_review(stage,texts)
    if found is None or len(found["retakes"])!=1:
        return None
    n,index=found["retakes"][0]
    original=[row["original_blind_transcripts"] for row in found["trace"]["slides"]]
    def archive(i):
        def reader(path):
            number=int(path.stem.removeprefix("slide"))
            if (path!=stage/f"slide{number}.wav" or
                    not 1<=number<=len(original)):
                raise SourceOperatorCueRecoveryError(
                    "Historical WAV replay has wrong identity")
            return original[number-1][i]
        return reader
    report=audit_with_recognizer(
        stage,texts,archive(0),lambda x:x,
        independent_recognizer=archive(1),
        recognition_models=found["models"])
    selected=choose_material_operator_cues(stage,report,texts)
    if selected!={n:[2]} and (
            len(selected)!=1 or list(selected)!=[n]
            or len(selected[n])!=1):
        return None
    # Require exact documented historical contrary retake. It cannot become
    # an authorization for more ASR on the same unchanged audio; it can
    # motivate only one new source-immutable cue WAV.
    from microgen_tts_acoustic_qa import _input_snapshot
    snapshot=_input_snapshot(stage,len(texts))
    bound={
        "source_sha256":sha(stage/"source.pdf"),
        "input_snapshot_sha256":found["trace"]["source_snapshot_sha256"],
        "original_private_trace_sha256":sha(found["trace_path"]),
        "old_campaign":found["old"].parent.name,
        "models":list(found["models"]),
        "retake_slides":[{"slide":n,"reviewer_index":index}],
    }
    root=stage.parent.parent
    seen=[]
    for campaign in root.iterdir():
        if (campaign==stage.parent or not campaign.is_dir()
                or campaign.is_symlink()):
            continue
        old=campaign/stage.name
        receipt=old/RECEIPT
        if receipt.is_symlink() or not receipt.is_file():
            continue
        owner=read_json(campaign/OWNER)
        if (not isinstance(owner,dict)
                or owner.get("publication_authorized") is not False
                or owner.get("scope",{}).get("host")!="hp"
                or owner.get("scope",{}).get("work_root")!=str(campaign)
                or owner.get("scope",{}).get("source_sha256")!=bound["source_sha256"]):
            continue
        data=read_json(receipt,128_000)
        if (not isinstance(data,dict)
                or data.get("publication_allowed") is not False
                or not isinstance(data.get("source_binding"),dict)):
            continue
        prior_binding=data["source_binding"]
        if any(prior_binding.get(key)!=bound[key] for key in (
                "source_sha256","input_snapshot_sha256",
                "original_private_trace_sha256","old_campaign","models")):
            continue
        # The earlier 2fe957f policy identified [5,7]; the later
        # meaning-preserving rule correctly drops harmless slide 7.
        # The historical rejected [5] spend still binds to the exact WAV
        # and MUST not disappear because the other item is now resolved.
        scheduled=prior_binding.get("retake_slides",[])
        if (not isinstance(scheduled,list) or
                {"slide":n,"reviewer_index":index} not in scheduled):
            continue
        attempts=data.get("attempts",[])
        if (not isinstance(attempts,list) or
                len(attempts)!=len(scheduled)):
            continue
        rejected=[a for a in attempts if (
            isinstance(a,dict) and a.get("slide")==n and
            a.get("reviewer_index")==index and
            a.get("status")=="REJECTED" and
            isinstance(a.get("transcript"),str))]
        if len(rejected)!=1:
            continue
        if any(a.get("status") not in ("REJECTED","NOT_SENT")
               for a in attempts if isinstance(a,dict)):
            continue
        seen.append((old,receipt))
    if len(seen)!=1 or snapshot!=bound["input_snapshot_sha256"]:
        return None
    return {"found":found,"report":report,"selected":selected,
            "rejected":seen[0],"binding":bound}


def _voice_once(text:str,target:Path,record:dict)->None:
    """One Gemini model, one key slot, one SDK try; no provider fallback."""
    from microgen_flash_tts import (
        _load_gemini_keys_from_microvid,_response_wav,STYLE,
    )
    from gemini_keys import get_gemini_api_keys,create_gemini_client
    from gemini_lane import gemini_lane
    from microgen_tts_provenance import wav_characteristics
    import re
    model=ALLOWED_PROVIDER.get(record["provider"])
    voice=record.get("voice_name")
    if (model is None or not isinstance(voice,str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}",voice)):
        raise SourceOperatorCueRecoveryError("Pinned Gemini voice/provider mismatch")
    _load_gemini_keys_from_microvid()
    keys=get_gemini_api_keys()
    position=int(os.getenv("MICROGEN_GEMINI_PREFERRED_KEY_INDEX","1"))-1
    if not 0<=position<len(keys):
        raise SourceOperatorCueRecoveryError("Selected single Gemini key absent")
    if int(os.getenv("MICROGEN_GEMINI_SDK_RETRY_ATTEMPTS","1"))!=1:
        raise SourceOperatorCueRecoveryError("SDK retry budget must be one")
    # The failure history is a compressed/omitted division operator.
    # This is a *delivery instruction*, not a change to the source words.
    # The source-blind Gemini reviewers must still hear the exact operation.
    style=STYLE+(
        " Articulate every mathematical operator completely. For the "
        "division expression, clearly say the two separate words "
        "'divided by', with a brief natural pause before the denominator. "
        "Do not omit an operator, alter signs/numbers or add new content."
    )
    with gemini_lane("source_operator_single_cue_tts",model):
        client=create_gemini_client(keys[position])
        reply=client.models.generate_content(
            model=model,contents=[{"role":"user","parts":[
                {"text":text,"speech_metadata":{"style":style}}
            ]}],config={"response_modalities":["AUDIO"],
                        "speech_config":{"voice_config":{
                            "voice":record["voice_name"]}}})
        payload=_response_wav(reply)
    if target.exists() or target.is_symlink():
        raise SourceOperatorCueRecoveryError("Cue candidate path already exists")
    with target.open("xb") as dest:
        dest.write(payload)
        dest.flush()
        os.fsync(dest.fileno())
    actual=wav_characteristics(target)
    if (actual["sample_rate_hz"]!=record["sample_rate_hz"]
            or actual["channels"]!=record["channels"]):
        raise SourceOperatorCueRecoveryError(
            "Generated cue violates voice sample identity")


def maybe_repair_rejected_operator(stage:Path,texts:list[str],
              *,synthesize=None,recognizer_factory=None):
    """Finite production repair; returns independent acoustic receipt or None.

    No candidate audio/media modification is permitted on failed review.
    An interrupted reserved paid request always becomes a mandatory hold.
    """
    from microgen_verified_acoustic_replay import sha
    from microgen_autonomous_acoustic_gate import _normalized,_verify,_providers
    from microgen_tts_acoustic_qa import (
        mismatch_details,audit_with_recognizer,verified_minor_asr_variation,
    )
    from microgen_tts_provenance import (
        verify_manifest,make_record,write_manifest,
    )
    from microgen_timed_acoustic_repair import prepare_timed_repair
    from microgen_timed_highlight_contract import inspect_timed_highlights
    from microgen_timed_acoustic_transaction import install_timed_acoustic
    from microgen_quality import check_wavs
    import shutil

    stage=Path(stage)
    if (stage/JOURNAL).exists() or (stage/JOURNAL).is_symlink():
        raise SourceOperatorCueRecoveryError(
            "PRIOR_SOURCE_OPERATOR_TTS_RESERVATION_HOLD: "
            "one-send recovery journal exists; no new paid calls")
    if stage.is_symlink() or not stage.is_dir() or _normalized(stage)!=texts:
        return None
    selection=_eligible(stage,texts)
    if selection is None:
        return None
    found=selection["found"]
    n=found["retakes"][0][0]
    selected=selection["selected"]
    provider=verify_manifest(stage,texts)["slides"]
    if (provider[n-1]["provider"] not in ALLOWED_PROVIDER
            or any((r["provider"],r["voice_name"],r["sample_rate_hz"])
                   !=(provider[n-1]["provider"],provider[n-1]["voice_name"],
                      provider[n-1]["sample_rate_hz"]) for r in provider)):
        raise SourceOperatorCueRecoveryError("Cross-voice source cue not safe")
    bound={
        **selection["binding"],
        "rejected_receipt_sha256":sha(selection["rejected"][1]),
        "source_wav_sha256":sha(stage/f"slide{n}.wav"),
        "cue_original_sha256":sha(stage/"highlight_chunks"/
            f"slide{n}_cue{selected[n][0]}.wav"),
        "selected_cues":{str(n):selected[n]},
        "code_sha256":sha(Path(__file__)),
        "voice_provider":provider[n-1]["provider"],
        "voice_name":provider[n-1]["voice_name"],
    }
    target=stage/JOURNAL
    if target.exists() or target.is_symlink():
        raise SourceOperatorCueRecoveryError(
            "PRIOR_SOURCE_OPERATOR_TTS_RESERVATION_HOLD: "
            "uncertain paid requests cannot be repeated")
    state={"schema_version":1,"publication_allowed":False,
           "binding":bound,"status":"STARTED","requests":[]}
    _write(stage,state,exclusive=True)
    scratch=stage.parent/(".microgen-single-operator-cue-"+sha(
        stage/"source.pdf")[:10]+"-"+str(n))
    if scratch.exists() or scratch.is_symlink():
        raise SourceOperatorCueRecoveryError(
            "Existing source-bound cue candidate requires offline reconciliation")
    scratch.mkdir()
    transcripts={}
    models=found["models"]
    engines=None

    def single_cue(text: str, wav:Path, old_record:dict):
        nonlocal state
        state["status"]="TTS_RESERVED"
        state["requests"].append({"kind":"TTS","model":
                 ALLOWED_PROVIDER[old_record["provider"]],"status":"RESERVED"})
        _write(stage,state)
        (synthesize or _voice_once)(text,wav,old_record)
        if not wav.is_file() or wav.is_symlink():
            raise SourceOperatorCueRecoveryError("TTS request produced no candidate")
        if _sha(wav)==bound["cue_original_sha256"]:
            raise SourceOperatorCueRecoveryError(
                "UNCHANGED_CUE_PCM_HOLD: refused to bill acoustic reviewers "
                "on the exact previously rejected mathematical cue")
        state["requests"][-1]["status"]="COMPLETE"
        state["requests"][-1]["wav_sha256"]=_sha(wav)
        state["status"]="TTS_COMPLETE"
        _write(stage,state)

    def blind_candidate(wav:Path,expected:str)->bool:
        nonlocal engines
        if engines is None:
            if recognizer_factory is None:
                first,second,names=_providers(
                    models_override=models,single_slot_only=True)
            else:
                first,second,names=recognizer_factory()
            if tuple(names)!=models:
                raise SourceOperatorCueRecoveryError(
                    "Independent reviewer identities changed")
            engines=(first,second)
        for i in (0,1):
            state["status"]=f"ASR{i+1}_RESERVED"
            state["requests"].append({
                "kind":"ASR","model":models[i],"status":"RESERVED",
                "candidate_sha256":_sha(wav)})
            _write(stage,state)
            transcript=str(engines[i](wav)).strip()
            if not 5<=len(transcript)<=12000:
                raise SourceOperatorCueRecoveryError("Empty blind source review")
            state["requests"][-1]["status"]="COMPLETE"
            state["requests"][-1]["transcript"]=transcript
            transcripts[i]=transcript
            state["status"]=f"ASR{i+1}_COMPLETE"
            _write(stage,state)
        a,b=transcripts[0],transcripts[1]
        scores=[mismatch_details(expected,t) for t in (a,b)]
        pair=mismatch_details(a,b)
        safe=(all(not score["sensitive_mismatches"]
                  and not score["circa_red_flags"]
                  and not score["letter_y_yay_red_flags"]
                  and score["difference_fraction_upper_bound"]<=.05
                  for score in scores)
              and (pair["difference_fraction_upper_bound"]<=.05 or
                   verified_minor_asr_variation(expected,a,b)))
        state["status"]="ASR_SOURCE_CONFIRMED" if safe else "ASR_REJECTED"
        _write(stage,state)
        return safe

    result=prepare_timed_repair(
        stage,[n],texts,provider,scratch,single_cue,blind_candidate,
        selected_cues=selected)
    if state["status"]!="ASR_SOURCE_CONFIRMED":
        raise SourceOperatorCueRecoveryError(
            "Candidate has no independently confirmed math speech")
    # Candidate is now source/PCM/timing verified, but ORIGINAL stage is
    # still untouched. Prepare complete voice provenance for atomic commit.
    for i in range(1,len(texts)+1):
        if i!=n:
            shutil.copy2(stage/f"slide{i}.wav",scratch/f"slide{i}.wav")
    record_list=[]
    for i,row in enumerate(provider,1):
        if i==n:
            row=make_record(
                slide=i,path=scratch/f"slide{i}.wav",text=texts[i-1],
                provider=row["provider"],key=row["key"],
                voice_name=row["voice_name"],
                language_code=row["language_code"],
                speaking_rate=row["speaking_rate"],location=row["location"])
        record_list.append(row)
    write_manifest(scratch,record_list,texts)
    verify_manifest(scratch,texts)
    from microgen_tts_acoustic_qa import _input_snapshot
    if (_input_snapshot(stage,len(texts)) !=
            selection["binding"]["input_snapshot_sha256"]):
        raise SourceOperatorCueRecoveryError("Original audio changed during repair")
    replacement={
        f"slide{n}.wav":scratch/f"slide{n}.wav",
        ".microgen_tts_provenance.json":
            scratch/".microgen_tts_provenance.json",
        ".microgen_timed_highlights.json":result["manifest"],
    }
    meta=scratch/f"slide{n}.json"
    meta.write_text(json.dumps(record_list[n-1],indent=2),encoding="utf8")
    replacement[f".microgen_tts_cache/slide{n}.json"]=meta
    replacement.update(result["chunks"])
    def validate():
        verify_manifest(stage,texts)
        check_wavs(stage,len(texts))
        inspect_timed_highlights(stage)
    install_timed_acoustic(stage,replacement,validate)
    state["status"]="SOURCE_BOUND_PCM_INSTALLED"
    state["accepted_wav_sha256"]=_sha(stage/f"slide{n}.wav")
    state["accepted_cue_sha256"]=_sha(
        stage/"highlight_chunks"/f"slide{n}_cue{selected[n][0]}.wav")
    _write(stage,state)
    original=[row["original_blind_transcripts"]
              for row in found["trace"]["slides"]]
    def replay(index):
        def srcblind(wav):
            j=int(wav.stem.removeprefix("slide"))
            if wav!=stage/f"slide{j}.wav" or not 1<=j<=len(texts):
                raise SourceOperatorCueRecoveryError("Wrong replay WAV")
            return transcripts[index] if j==n else original[j-1][index]
        return srcblind
    report=audit_with_recognizer(
        stage,texts,replay(0),lambda value:value,
        independent_recognizer=replay(1),
        recognition_models=models)
    _verify(stage,report,texts)
    state["status"]="INDEPENDENT_ACOUSTIC_QA_PASSED"
    _write(stage,state)
    from microgen_autonomous_acoustic_gate import RECEIPT as QA_RECEIPT
    receipt={
        "schema_version":1,
        "status":"AUTONOMOUS_INDEPENDENT_ASR_SCREEN_PASSED",
        "slide_count":len(texts),
        "recognition_models":report["recognition_models"],
        "repaired_audio_slides":1,
        "source_inputs":{
            "script_tts_sha256":_sha(stage/"script_tts.json"),
            "tts_provenance_sha256":_sha(stage/".microgen_tts_provenance.json")},
        "independent_report":report,
        "verified_source_operator_cue_recovery":{
            "journal_sha256":_sha(target),
            "prior_private_trace_sha256":_sha(found["trace_path"]),
            "selected_cues":{str(n):selected[n]},
            "publication_allowed":False},
        "automatic_technical_review":True,
        "human_approval_required":False,
        "pronunciation_perfection_certified":False,
        "publication_allowed":False,
    }
    with (stage/QA_RECEIPT).open("x",encoding="utf8") as f:
        json.dump(receipt,f,ensure_ascii=False,indent=2)
    return receipt


def verify_source_operator_repair(stage:Path,receipt:dict)->None:
    """Cryptographically re-attest historical + fresh blind evidence for video."""
    from microgen_verified_acoustic_replay import (
        valid_trace,read_json,OWNER,
    )
    from microgen_tts_acoustic_qa import mismatch_details
    from microgen_autonomous_acoustic_gate import _normalized
    stage=Path(stage)
    evidence=receipt.get("verified_source_operator_cue_recovery")
    if evidence is None:
        return
    if (not isinstance(evidence,dict)
            or set(evidence)!={"journal_sha256","prior_private_trace_sha256",
                               "selected_cues","publication_allowed"}
            or evidence.get("publication_allowed") is not False
            or receipt.get("repaired_audio_slides")!=1
            or not isinstance(evidence.get("selected_cues"),dict)
            or len(evidence["selected_cues"])!=1):
        raise SourceOperatorCueRecoveryError("Invalid source operator evidence")
    path=stage/JOURNAL
    state=read_json(path,150_000)
    if (path.is_symlink() or state is None
            or _sha(path)!=evidence["journal_sha256"]
            or state.get("schema_version")!=1
            or state.get("publication_allowed") is not False
            or state.get("status")!="INDEPENDENT_ACOUSTIC_QA_PASSED"):
        raise SourceOperatorCueRecoveryError("Unverifiable private operator journal")
    bound=state.get("binding")
    if not isinstance(bound,dict):
        raise SourceOperatorCueRecoveryError("Missing source/operator lineage")
    chosen=evidence["selected_cues"]
    if chosen!=bound.get("selected_cues"):
        raise SourceOperatorCueRecoveryError("Selected mathematical cue changed")
    n=int(next(iter(chosen)))
    indices=chosen[str(n)]
    if (type(n) is not int or not isinstance(indices,list)
            or len(indices)!=1 or type(indices[0]) is not int
            or indices[0]<1 or n<1 or n>receipt["slide_count"]):
        raise SourceOperatorCueRecoveryError("Incorrect repaired cue scope")
    j=indices[0]
    if (bound.get("source_sha256")!=_sha(stage/"source.pdf")
            or bound.get("code_sha256")!=_sha(stage/
                "microgen_source_operator_cue_recovery.py")
            or state.get("accepted_wav_sha256")!=_sha(stage/f"slide{n}.wav")
            or state.get("accepted_cue_sha256")!=_sha(
                stage/"highlight_chunks"/f"slide{n}_cue{j}.wav")
            or state.get("accepted_wav_sha256")==bound.get("source_wav_sha256")
            or state.get("accepted_cue_sha256")==bound.get("cue_original_sha256")):
        raise SourceOperatorCueRecoveryError(
            "Source operator correction not a verified fresh PCM asset")
    requests=state.get("requests")
    if (not isinstance(requests,list) or len(requests)!=3
            or [v.get("kind") for v in requests]!=["TTS","ASR","ASR"]
            or any(v.get("status")!="COMPLETE" for v in requests)
            or requests[0].get("wav_sha256")==bound.get("cue_original_sha256")
            or requests[1].get("model")!=bound["models"][0]
            or requests[2].get("model")!=bound["models"][1]
            or requests[1].get("candidate_sha256")!=
                state["accepted_wav_sha256"]
            or requests[2].get("candidate_sha256")!=
                state["accepted_wav_sha256"]):
        raise SourceOperatorCueRecoveryError(
            "Falsified or incomplete paid provider provenance")
    report=receipt.get("independent_report")
    if (not isinstance(report,dict)
            or report.get("review_required_slides")!=[]
            or report.get("recognition_models")!=bound["models"]):
        raise SourceOperatorCueRecoveryError("Missing independent acoustic report")
    rows=report.get("slides",[])
    if not isinstance(rows,list) or len(rows)!=receipt["slide_count"]:
        raise SourceOperatorCueRecoveryError("Incomplete slide acoustic receipts")
    if rows[n-1]["transcripts"]!=[
        requests[1]["transcript"],requests[2]["transcript"]
    ]:
        raise SourceOperatorCueRecoveryError("Repaired slide transcripts drifted")
    texts=_normalized(stage)
    for transcript in rows[n-1]["transcripts"]:
        d=mismatch_details(texts[n-1],transcript)
        if (d["sensitive_mismatches"] or d["circa_red_flags"]
                or d["letter_y_yay_red_flags"]
                or d["difference_fraction_upper_bound"]>.05):
            raise SourceOperatorCueRecoveryError("Math operator not recognized")
    root=stage.parent.parent
    old=root/bound["old_campaign"]/stage.name
    old_trace_paths=list(old.glob(".microgen_private_acoustic_failed_*.json"))
    old_trace_paths=[
        p for p in old_trace_paths
        if not p.is_symlink()
        and _sha(p)==bound["original_private_trace_sha256"]
    ]
    if (len(old_trace_paths)!=1 or
            evidence["prior_private_trace_sha256"]!=
                bound["original_private_trace_sha256"]):
        raise SourceOperatorCueRecoveryError("Old independent blind trace absent")
    trace=valid_trace(
        old_trace_paths[0],bound["input_snapshot_sha256"],
        receipt["slide_count"],tuple(bound["models"]))
    if trace is None:
        raise SourceOperatorCueRecoveryError("Historical two-model trace invalid")
    for index,row in enumerate(rows,1):
        if index==n:
            continue
        prior=trace["slides"][index-1]
        if (row["audio_sha256"]!=prior["wav_sha256"]
                or row["transcripts"]!=prior["original_blind_transcripts"]):
            raise SourceOperatorCueRecoveryError(
                f"Unmodified slide {index} has ungrounded blind evidence")
    from microgen_timed_highlight_contract import inspect_timed_highlights
    inspect_timed_highlights(stage)
