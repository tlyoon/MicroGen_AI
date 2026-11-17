"""Conservative source-bound voice-only recovery of repeated physics-component ASR.

Invoked in the NORMAL private narration postflight, before any new TTS call.
Never rewrites raw lecture narration, printed math, slide PDF or prior WAVs.
Requires original independently obtained two-Gemini blind evidence on the exact
same source and spoken script. A new voice transcript is NOT acoustic approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import tempfile

RECEIPT=".microgen_source_bound_voice_recovery.json"
ORIGINAL=".microgen_original_voice_sidecar.json"
PROPOSAL=".microgen_proposed_voice_sidecar.json"
MAX_HISTORICAL_DIRS=120


class SourceBoundVoiceRecoveryError(RuntimeError):
    pass


def sha(path:Path)->str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def read(path:Path,limit=200_000)->dict|None:
    if (path.is_symlink() or not path.is_file()
            or not 1<=path.stat().st_size<=limit):
        return None
    try:
        obj=json.loads(path.read_text(encoding="utf8"))
    except (OSError,UnicodeError,ValueError):
        return None
    return obj if isinstance(obj,dict) else None


def clarify_x_component(text:str)->str:
    """Expand ONLY the same explicitly named x-component variable."""
    if not isinstance(text,str):
        raise TypeError("Voice content must be text")
    result=text
    # Replace specific roles BEFORE the generic component, preserving exact
    # original initial/final index, speaker identity, and all quantities.
    rules=(
      (r"\bdee\s+vee\s+(?:sub\s+)?ex\s+over\s+dee\s+tee\b",
       "the time derivative of the x component of velocity"),
      (r"\bvelocity\s+vee\s+(?:sub\s+)?ex\s+(?:eye|initial)\b",
       "initial velocity along the x axis"),
      (r"\bvelocity\s+vee\s+(?:sub\s+)?ex\s+(?:eff|final)\b",
       "final velocity along the x axis"),
      (r"\bacceleration\s+ay\s+(?:sub\s+)?ex\s+(?:avg|average)\b",
       "average acceleration along the x axis"),
      (r"\bvelocity\s+vee\s+(?:sub\s+)?ex\b",
       "velocity along the x axis"),
      (r"\bacceleration\s+ay\s+(?:sub\s+)?ex\b",
       "acceleration along the x axis"),
      (r"\bvee\s+(?:sub\s+)?ex\s+(?:eye|initial)\b",
       "the initial x component of velocity"),
      (r"\bvee\s+(?:sub\s+)?ex\s+(?:eff|final)\b",
       "the final x component of velocity"),
      (r"\bvee\s+(?:sub\s+)?ex\s+car\b",
       "the car's x component of velocity"),
      (r"\bvee\s+(?:sub\s+)?ex\s+trooper\b",
       "the trooper's x component of velocity"),
      (r"\bay\s+(?:sub\s+)?ex\s+(?:avg|average)\b",
       "the average x component of acceleration"),
      (r"\bvee\s+(?:sub\s+)?ex\b",
       "the x component of velocity"),
      (r"\bay\s+(?:sub\s+)?ex\b",
       "the x component of acceleration"),
    )
    for pattern,speech in rules:
        result=re.sub(pattern,speech,result,flags=re.I)
    return result


def _source_bound_blind_evidence(stage:Path, texts:list[str])->dict|None:
    """Find an original verified two-Gemini failure on these EXACT words."""
    from microgen_tts_acoustic_qa import _input_snapshot
    from microgen_verified_acoustic_replay import valid_trace
    from text_to_speech_v25 import normalize_scientific_speech

    root=Path(os.environ.get("LOCALAPPDATA","/not-configured"))/"MicroGen_AI_Checkpoints"
    if (os.name!="nt" or socket.gethostname().casefold()!="hp"
            or stage.parent.parent!=root):
        return None
    grant=read(stage.parent/".microgen_bounded_provider_authorization.json")
    checkpoint=read(stage/".microgen_checkpoint.json")
    if grant is None or checkpoint is None:
        return None
    scope=grant.get("scope",{})
    source=stage/"source.pdf"
    if source.is_symlink() or not source.is_file():
        return None
    source_digest=sha(source)
    if (not isinstance(scope,dict)
            or scope.get("work_root")!=str(stage.parent)
            or scope.get("host")!="hp"
            or scope.get("stop_after")!="acceptance"
            or scope.get("source_sha256")!=source_digest
            or scope.get("code_revision")!=checkpoint.get("package_commit")
            or grant.get("publication_authorized") is not False):
        return None
    dirs=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
          and p!=stage.parent and not p.name.startswith(".")]
    # Avoid unbounded file tree work. Only root-level potential private
    # campaigns count, never ordinary files in the checkpoint directory.
    candidate_dirs=[p for p in dirs if
                    (p/".microgen_bounded_provider_authorization.json").is_file()]
    if len(candidate_dirs)>MAX_HISTORICAL_DIRS:
        raise SourceBoundVoiceRecoveryError("Historical voice campaign bound exceeded")
    eligible=[]
    for parent in sorted(candidate_dirs):
        oldgrant=read(parent/".microgen_bounded_provider_authorization.json")
        if oldgrant is None:
            continue
        oldscope=oldgrant.get("scope",{})
        old=parent/stage.name
        oldcp=read(old/".microgen_checkpoint.json")
        oldsrc=old/"source.pdf"
        oldside=read(old/"script_tts.json",limit=600_000)
        if (not isinstance(oldscope,dict)
                or oldscope.get("work_root")!=str(parent)
                or oldscope.get("host")!="hp"
                or oldscope.get("source_sha256")!=source_digest
                or oldscope.get("stop_after")!="acceptance"
                or oldgrant.get("publication_authorized") is not False
                or oldcp is None
                or oldcp.get("package_commit")!=oldscope.get("code_revision")
                or not oldcp.get("completed",{}).get("tts")
                or not oldsrc.is_file() or oldsrc.is_symlink()
                or sha(oldsrc)!=source_digest
                or not oldside):
            continue
        earlier=oldside.get("slides")
        if (not isinstance(earlier,list) or len(earlier)!=len(texts)
                or any(not isinstance(row,dict)
                       or not isinstance(row.get("tts_text"),str)
                       or normalize_scientific_speech(row["tts_text"])!=text
                       for row,text in zip(earlier,texts))):
            continue
        snapshot=_input_snapshot(old,len(texts))
        for tracepath in old.glob(".microgen_private_acoustic_failed_*.json"):
            raw=read(tracepath)
            if raw is None:
                continue
            models=raw.get("models")
            if (not isinstance(models,list) or len(models)!=2
                    or models[0]==models[1]
                    or not all(isinstance(m,str) and m.startswith("gemini-")
                               for m in models)):
                continue
            trace=valid_trace(tracepath,snapshot,len(texts),tuple(models))
            if (trace is None
                    or any(row["expected_spoken_sha256"]!=
                           hashlib.sha256(text.encode("utf8")).hexdigest()
                           for row,text in zip(trace["slides"],texts))):
                continue
            # Require repeated *observed* component letter ambiguity from
            # independent blind ASR, not simply the presence of x variables
            # in the planned narration. Never infer the audio is correct.
            problem_slides=set()
            for n,(text,row) in enumerate(zip(texts,trace["slides"]),1):
                if not re.search(r"\b(?:vee|ay)\s+(?:sub\s+)?ex\b",text,re.I):
                    continue
                if any(re.search(r"\b(?:v of x|a sub (?:a y|y e|y x))\b",
                                 heard,re.I)
                       for heard in row["original_blind_transcripts"]):
                    problem_slides.add(n)
            if len(problem_slides)<2:
                continue
            eligible.append({
                "origin":parent.name,
                "trace_sha256":sha(tracepath),
                "original_source_sha256":source_digest,
                "observed_disagreement_slides":sorted(problem_slides),
            })
    if not eligible:
        return None
    identities={(a["trace_sha256"],a["original_source_sha256"])
                for a in eligible}
    if len(identities)!=1:
        raise SourceBoundVoiceRecoveryError(
            "Conflicting historical independent acoustic source witnesses")
    return min(eligible,key=lambda a:a["origin"])


def _verify_completed(stage:Path)->dict|None:
    evidence=read(stage/RECEIPT)
    if evidence is None:
        if any((stage/name).exists() or (stage/name).is_symlink()
               for name in (ORIGINAL,PROPOSAL)):
            raise SourceBoundVoiceRecoveryError(
                "Unjournaled source voice repair cannot be accepted")
        return None
    sidecar=stage/"script_tts.json"
    original=stage/ORIGINAL
    proposal=stage/PROPOSAL
    if (evidence.get("schema_version")!=1
            or evidence.get("publication_allowed") is not False
            or evidence.get("paid_model_calls")!=0
            or not isinstance(evidence.get("source_sha256"),str)
            or evidence["source_sha256"]!=sha(stage/"source.pdf")
            or evidence.get("policy_sha256")!=sha(stage/
                     "microgen_source_bound_voice_recovery.py")
            or original.is_symlink() or not original.is_file()
            or evidence.get("original_sidecar_sha256")!=sha(original)
            or sidecar.is_symlink() or not sidecar.is_file()
            or evidence.get("status") not in ("PREPARED","RECOVERED_SOURCE_BOUND_SPEECH")):
        raise SourceBoundVoiceRecoveryError("Unverifiable voice-recovery transaction")
    if evidence["status"]=="RECOVERED_SOURCE_BOUND_SPEECH":
        if (sha(sidecar)!=evidence.get("repaired_sidecar_sha256")
                or proposal.exists()):
            raise SourceBoundVoiceRecoveryError("Repaired voice sidecar changed")
        return {"status":evidence["status"],
                "changed_slides":evidence["changed_slides"],
                "restarted":True}
    # Interrupted transaction. The only safe states are old or intended
    # bytes. Never infer permission to modify any unknown/different script.
    if (not proposal.is_file() or proposal.is_symlink()
            or sha(proposal)!=evidence.get("repaired_sidecar_sha256")
            or sha(sidecar) not in (evidence["original_sidecar_sha256"],
                                   evidence["repaired_sidecar_sha256"])):
        raise SourceBoundVoiceRecoveryError("Incomplete source voice transaction")
    if sha(sidecar)==evidence["original_sidecar_sha256"]:
        os.replace(proposal,sidecar)
    else:
        proposal.unlink()
    evidence["status"]="RECOVERED_SOURCE_BOUND_SPEECH"
    _atomic_receipt(stage,evidence)
    return {"status":evidence["status"],
            "changed_slides":evidence["changed_slides"],
            "restarted":True}


def _atomic_receipt(stage:Path,evidence:dict)->None:
    receipt=stage/RECEIPT
    temp=stage/(RECEIPT+".tmp")
    if temp.exists() or temp.is_symlink():
        raise SourceBoundVoiceRecoveryError("Voice recovery receipt temp conflict")
    with temp.open("x",encoding="utf8") as stream:
        json.dump(evidence,stream,indent=2,sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp,receipt)


def recover_disputed_component_voice(stage:Path)->dict:
    stage=Path(stage).resolve()
    if not stage.is_dir() or stage.is_symlink():
        raise SourceBoundVoiceRecoveryError("Unsafe private narration stage")
    if not (stage/RECEIPT).exists():
        original_copy=stage/ORIGINAL
        planned=stage/PROPOSAL
        if original_copy.is_file() and not original_copy.is_symlink():
            # A crash before the durable receipt and before the sidecar
            # commit is fully reversible; no external call or QA receipt
            # was issued. Restore the safe source-only operation in flight.
            if (sha(original_copy)==sha(stage/"script_tts.json")
                    and not planned.is_symlink()):
                planned.unlink(missing_ok=True)
                original_copy.unlink()
    prior=_verify_completed(stage)
    if prior is not None:
        return prior
    for name in (ORIGINAL,PROPOSAL,RECEIPT):
        if (stage/name).exists() or (stage/name).is_symlink():
            raise SourceBoundVoiceRecoveryError("Unjournaled partial voice repair")
    from microgen_reviewed_math_voice import (
        voice_input_risk_status,preflight_voice_sidecar,
    )
    from microgen_timed_cue_planner import _require_budget_preflight
    from microgen_cue_semantic_mapping import numbers
    from text_to_speech_v25 import normalize_scientific_speech
    from microgen_quality import check_narration

    sidecar=stage/"script_tts.json"
    original=read(sidecar,limit=600_000)
    if original is None:
        raise SourceBoundVoiceRecoveryError("Narration sidecar missing or invalid")
    oldrows=original.get("slides")
    if (not isinstance(oldrows,list) or len(oldrows)<2 or len(oldrows)>200
            or [row.get("slide") for row in oldrows] !=
               list(range(1,len(oldrows)+1))):
        raise SourceBoundVoiceRecoveryError("Unverifiable narration slide order")
    texts=[normalize_scientific_speech(str(row.get("tts_text") or ""))
           for row in oldrows]
    bound=_source_bound_blind_evidence(stage,texts)
    if bound is None:
        return {"status":"NO_VERIFIED_HISTORICAL_ASR_VOICE_ABSTAINED",
                "changed_slides":[],"restarted":False}
    revised=copy.deepcopy(original)
    changed=[]
    for old,row in zip(oldrows,revised["slides"]):
        prior_text=old["tts_text"]
        # Narrator-side TTS text is always the speech-normalized fixed
        # point, not raw mathematics notation. A literal "x component"
        # would trigger the correct prepayment ambiguous-letter guard.
        repaired=normalize_scientific_speech(
            clarify_x_component(prior_text))
        if repaired==prior_text:
            continue
        if (clarify_x_component(repaired)!=repaired
                or numbers(repaired)!=numbers(prior_text)):
            raise SourceBoundVoiceRecoveryError(
                "Source voice clarification changed numerical evidence")
        row["tts_text"]=repaired
        row["tts_math_voice_preflight"]=voice_input_risk_status(
            repaired,normalize_scientific_speech)
        if row["tts_math_voice_preflight"]["unresolved_source_risk_count"]:
            raise SourceBoundVoiceRecoveryError(
                "Voice clarification retained predictable pronunciation risks")
        changed.append(row["slide"])
    if len(changed)<2:
        return {"status":"NO_REPEATED_EXACT_COMPONENT_VOICE_ABSTAINED",
                "changed_slides":[],"restarted":False}
    # Mandatory full 21-slide source, numeric and fixed semantic-budget
    # admission BEFORE changing a single published/reusable narration byte.
    with tempfile.TemporaryDirectory(prefix=".microgen-source-voice-check-",
                                     dir=stage.parent) as directory:
        candidate=Path(directory)
        for name in ["source.pdf","slides.pdf","script.txt","slides.tex"]:
            shutil.copy2(stage/name,candidate/name)
        for n in range(1,len(oldrows)+1):
            shutil.copy2(stage/f"slide{n}.pdf",candidate/f"slide{n}.pdf")
        payload=json.dumps(revised,indent=2,ensure_ascii=False)
        (candidate/"script_tts.json").write_text(payload,encoding="utf8")
        check_narration(candidate/"script.txt",candidate/"script_tts.json",
                        len(oldrows))
        # The source/PDF math cue matcher may ask Gemini only within the
        # frozen four-slide semantic budget. Never increase the limit.
        from microgen_private_dev_policy import MAX_SEMANTIC_SLIDES
        _require_budget_preflight(
            candidate,semantic_limit=MAX_SEMANTIC_SLIDES,max_cues=120)
        preflight_voice_sidecar(candidate,require_policy_binding=True)
    evidence={
        "schema_version":1,
        "status":"PREPARED",
        "source_sha256":sha(stage/"source.pdf"),
        "original_sidecar_sha256":sha(sidecar),
        "repaired_sidecar_sha256":hashlib.sha256(
            payload.encode("utf8")).hexdigest(),
        "policy_sha256":sha(stage/"microgen_source_bound_voice_recovery.py"),
        "historic_blind_transcript_sha256":bound["trace_sha256"],
        "historic_campaign":bound["origin"],
        "verified_observed_disagreement_slides":
            bound["observed_disagreement_slides"],
        "changed_slides":changed,
        "semantic_budget_limit":MAX_SEMANTIC_SLIDES,
        "original_source_pdf_modified":False,
        "independent_acoustic_qa_required":True,
        "paid_model_calls":0,
        "publication_allowed":False,
    }
    # Durable two-phase prepared transaction; a crash before or after the
    # atomic sidecar swap is reconciled against exact original/new SHA.
    shutil.copy2(sidecar,stage/ORIGINAL)
    # Write EXACT hashed UTF-8 bytes. Text-mode newline translation on
    # Windows otherwise changes LF to CRLF after the SHA was computed,
    # making an otherwise valid source-verified proposal unrepeatable.
    with (stage/PROPOSAL).open("xb") as stream:
        stream.write(payload.encode("utf8"))
        stream.flush()
        os.fsync(stream.fileno())
    if sha(stage/PROPOSAL)!=evidence["repaired_sidecar_sha256"]:
        raise SourceBoundVoiceRecoveryError("Unverifiable new voice sidecar bytes")
    _atomic_receipt(stage,evidence)
    result=_verify_completed(stage)
    result["restarted"]=False
    return result


def verify_source_voice_recovery(stage:Path)->dict|None:
    """Validate durable speech-only repair in normal narration stage QA.

    Absence is legitimate for a lecture without historical two-model evidence;
    a partial or drifted voice repair is NOT legitimate or publishable.
    """
    return _verify_completed(Path(stage))
