"""Source/WAV-bound, two-model Gemini acoustic QA for unattended development.

Independent ASR is a *screen*, never a proof of perfect pronunciation.
Only a clear, bounded, repeatable audio slip may cause one same-text,
same-engine/voice Gemini TTS regeneration. Source scripts are never edited.
Unknown, unavailable, high-risk or controversial utterances fail closed.
No human sign-off, local speech model, Cloud TTS fallback or publication.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Callable

from microgen_tts_acoustic_qa import (
    AcousticQAError, audit_with_recognizer, mismatch_details,
    gemini_audio_recognizer, _input_snapshot,
)
from microgen_tts_evidence import verify_acoustic_evidence
from microgen_tts_provenance import (
    verify_manifest, write_manifest, make_record, digest_file,
    TTSProvenanceError, inspect_normalized_input_drift,
)
from microgen_tts_wave_integrity import require_structurally_usable_audio
from microgen_quality import check_wavs, QualityError

RECEIPT=".microgen_autonomous_acoustic_qa.json"
MAX_REPAIR_SLIDES=2
MAX_DISAGREEMENT_RECHECK_SLIDES=2
DEFAULT_MODELS=("gemini-3.5-flash", "gemini-3.8-flash")
PASS="ASR_SCREEN_PASS_LISTENING_REQUIRED"
REPAIRABLE="REVIEW_REQUIRED_PRONUNCIATION_RISK"


class AutonomousAcousticError(QualityError):
    pass


def _normalized(stage: Path) -> list[str]:
    from text_to_speech_v25 import normalize_scientific_speech
    sidecar=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=sidecar.get("slides")
    if (not isinstance(slides,list) or not slides or
        [i.get("slide") for i in slides]!=list(range(1,len(slides)+1))):
        raise AutonomousAcousticError("Malformed or reordered source TTS sidecar")
    texts=[normalize_scientific_speech(str(
        i.get("tts_text") or i.get("narration") or "")) for i in slides]
    if any(not t.strip() for t in texts):
        raise AutonomousAcousticError("Empty source-bound speech input")
    return texts


def _providers() -> tuple[Callable,Callable,tuple[str,str]]:
    from dotenv import load_dotenv
    from gemini_keys import get_gemini_api_keys
    config=Path(os.environ.get("MICROVID_CONFIG_DIR",
                    str(Path(os.environ["LOCALAPPDATA"])/"Microvid")))
    load_dotenv(config/".env",override=False)
    keys=get_gemini_api_keys()
    if not keys:
        raise AutonomousAcousticError("No configured Gemini keys")
    raw=os.environ.get("MICROGEN_GEMINI_PREFERRED_KEY_INDEX","1")
    try:
        index=int(raw)-1
    except ValueError as exc:
        raise AutonomousAcousticError("Invalid configured Gemini key preference") from exc
    if not 0<=index<len(keys):
        raise AutonomousAcousticError("Preferred Gemini key index unavailable")
    models=(os.environ.get("MICROGEN_ACOUSTIC_MODEL_A",DEFAULT_MODELS[0]),
            os.environ.get("MICROGEN_ACOUSTIC_MODEL_B",DEFAULT_MODELS[1]))
    if models[0]==models[1] or not all(models):
        raise AutonomousAcousticError("Two distinct Gemini audio reviewers required")
    # Every independent model may use the configured key pool. Preserve
    # distinct model identities while avoiding repeat requests to a key that
    # has already failed during this model's recognition pass.
    ordered_keys = keys[index:] + keys[:index]

    def key_pool_recognizer(model:str) -> Callable:
        engines = [gemini_audio_recognizer(key,model=model)
                   for key in ordered_keys]
        preferred_slot = 0

        def transcribe(wav:Path) -> str:
            nonlocal preferred_slot
            for offset in range(len(engines)):
                slot = (preferred_slot + offset) % len(engines)
                try:
                    transcript = str(engines[slot](wav)).strip()
                    if len(transcript) < 5:
                        raise AcousticQAError("Empty independent transcript")
                    preferred_slot = slot
                    return transcript
                except Exception as exc:
                    # Never log the credential or expected narration.
                    print(f"[Acoustic QA] {model} key slot #{slot+1} "
                          f"unavailable ({type(exc).__name__}); "
                          "trying next configured slot",flush=True)
            raise AutonomousAcousticError(
                f"Independent acoustic recognizer {model} unavailable "
                f"across {len(engines)} configured Gemini key slots")
        return transcribe

    return (key_pool_recognizer(models[0]),
            key_pool_recognizer(models[1]),models)


def _transcripts(stage: Path, texts: list[str], engines: tuple[Callable,Callable],
                 models: tuple[str,str], *, memo:dict) -> dict:
    def caching(index:int):
        def run(path:Path):
            key=(index,digest_file(path))
            if key not in memo:
                transcript=str(engines[index](path)).strip()
                # A short partial ASR response for a full-length lecture is
                # not evidence that the TTS stopped speaking. Recheck this
                # model ONCE, without passing the expected words to Gemini.
                from microgen_tts_acoustic_qa import tokens
                try:
                    slide=int(path.stem.removeprefix("slide"))
                    reference_words=len(tokens(texts[slide-1]))
                except (ValueError,IndexError):
                    reference_words=0
                if (reference_words>=25 and
                        len(tokens(transcript)) < 0.45*reference_words):
                    print(f"[Acoustic QA] model {models[index]} returned "
                          f"short partial transcript for {path.name}; "
                          "one independent recheck",flush=True)
                    try:
                        candidate=str(engines[index](path)).strip()
                        if len(tokens(candidate))>len(tokens(transcript)):
                            transcript=candidate
                    except Exception:
                        # The original partial response stays untrusted and
                        # the final acoustic report will fail closed.
                        pass
                memo[key]=transcript
            return memo[key]
        return run
    from text_to_speech_v25 import normalize_scientific_speech
    return audit_with_recognizer(
        stage,texts,caching(0),normalize_scientific_speech,
        independent_recognizer=caching(1),recognition_models=models)


def _recheck_disagreements(stage:Path, report:dict, texts:list[str],
                           engines:tuple[Callable,Callable],
                           models:tuple[str,str], memo:dict) -> dict:
    """At most two independent dual-model retakes of disputed audio.

    A recognizer's one-off transcription error must not become a fake TTS
    defect. Neither model sees the expected text. Both retakes must agree
    with each other AND with at least one original blind recognition.
    Every retake is compared to the original script by the strict screen
    afterwards; unresolved or sensitive mistakes still block acceptance.
    """
    disputed=[
        row for row in report.get("slides",[])
        if row["assessment"]=="REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE"
        and not row["source_pronunciation_risks"]
    ]
    if not disputed or len(disputed)>MAX_DISAGREEMENT_RECHECK_SLIDES:
        return report
    attempted=[]
    resolved=[]
    for row in disputed:
        n=row["slide"]
        wav=stage/f"slide{n}.wav"
        previous=row.get("transcripts",[])
        if len(previous)!=2 or any(not t for t in previous):
            continue
        attempted.append(n)
        retakes=[]
        for engine in engines:
            try:
                transcript=str(engine(wav)).strip()
                if len(transcript)<5 or any(
                        marker in transcript.lower()
                        for marker in ("[unclear]","[inaudible]")):
                    raise AutonomousAcousticError("Unreliable retake")
                retakes.append(transcript)
            except Exception:
                retakes=[]
                break
        if len(retakes)!=2:
            continue
        try:
            consensus=mismatch_details(retakes[0],retakes[1])
            has_original_support=any(
                mismatch_details(old,retakes[0])[
                    "difference_fraction_upper_bound"]<=0.05
                for old in previous)
            if (consensus["difference_fraction_upper_bound"]<=0.05
                    and has_original_support):
                fingerprint=digest_file(wav)
                for i in range(2):
                    memo[(i,fingerprint)]=retakes[i]
                resolved.append(n)
        except AcousticQAError:
            continue
    if resolved:
        report=_transcripts(stage,texts,engines,models,memo=memo)
    report["independent_disagreement_rechecks"]={
        "attempted_slides":attempted,"resolved_slides":resolved}
    return report


def _verify(stage:Path, report:dict, texts:list[str]) -> None:
    wav_hashes=[digest_file(stage/f"slide{i}.wav")
                for i in range(1,len(texts)+1)]
    bound=digest_file(stage/".microgen_tts_provenance.json")
    ok,reasons=verify_acoustic_evidence(report,stage,texts,wav_hashes,bound)
    if not ok:
        raise AutonomousAcousticError(
            "Independent acoustic evidence rejected: "+", ".join(reasons[:8]))
    if report["review_required_slides"]:
        raise AutonomousAcousticError("Unresolved acoustic discrepancies")


def _strict_candidate(candidate:Path, expected:str,
                      recognizers:tuple[Callable,Callable]) -> bool:
    transcripts=[]
    for recognizer in recognizers:
        try:
            value=str(recognizer(candidate)).strip()
            if len(value)<5:
                return False
            transcripts.append(value)
        except Exception:
            return False
    for speech in transcripts:
        findings=mismatch_details(expected,speech)
        if (findings["difference_fraction_upper_bound"]>0.05 or
            findings["sensitive_mismatches"] or findings["circa_red_flags"] or
            findings["letter_y_yay_red_flags"]):
            return False
    return (mismatch_details(*transcripts)["difference_fraction_upper_bound"]<=0.05)


def _render_same_voice(text:str, destination:Path, expected_record:dict) -> None:
    """Targeted same-model-family/voice TTS retry, no Cloud or model switching."""
    from microgen_flash_tts import render_batch
    with tempfile.TemporaryDirectory(prefix=".microgen-asr-render-",
                                     dir=destination.parent) as tmp:
        report=render_batch([text],Path(tmp)/"ready",
                  voice=expected_record["voice_name"],allow_cloud=False)
        if (report.get("engine")!=expected_record["provider"] or
            report.get("voice")!=expected_record["voice_name"]):
            raise AutonomousAcousticError("TTS rerender changed provider or voice")
        shutil.copy2(Path(tmp)/"ready"/"slide01.wav",destination)
    require_structurally_usable_audio(destination)


def _classify_review_blocker(report:dict) -> dict:
    """Categorize *evidence*, not putative audio defects, before auto-repair.

    Input is the existing source-bound independent two-model review. A math
    source risk or conflicting/absent recognition must never consume the
    limited same-voice TTS repair budget or be reported as a proven WAV error.
    This is a pure offline classifier: no model, ASR or TTS requests.
    """
    categories={
        "source_pronunciation_risk":[],
        "transcriber_disagreement":[],
        "recognition_unavailable":[],
        "repair_candidate":[],
        "other_ambiguous":[],
    }
    rows=report.get("slides",[])
    if not isinstance(rows,list):
        raise AutonomousAcousticError("Malformed independent acoustic report")
    flagged=report.get("review_required_slides",[])
    if (not isinstance(flagged,list) or any(type(n) is not int for n in flagged)
            or len(set(flagged))!=len(flagged)
            or any(n<1 or n>len(rows) for n in flagged)):
        raise AutonomousAcousticError("Invalid acoustic slide identities")
    for n in flagged:
        row=rows[n-1]
        if row.get("slide")!=n:
            raise AutonomousAcousticError("Acoustic report slide order mismatch")
        assessment=row.get("assessment")
        if row.get("source_pronunciation_risks"):
            categories["source_pronunciation_risk"].append(n)
        elif assessment=="REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE":
            categories["transcriber_disagreement"].append(n)
        elif assessment=="REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE":
            categories["recognition_unavailable"].append(n)
        elif assessment==REPAIRABLE:
            categories["repair_candidate"].append(n)
        else:
            categories["other_ambiguous"].append(n)
    if report.get("unavailable_recognizer_passes") or categories["recognition_unavailable"]:
        reason="INDEPENDENT_RECOGNIZER_UNAVAILABLE"
    elif categories["source_pronunciation_risk"]:
        reason="SOURCE_PRONUNCIATION_RISK_HOLD"
    elif categories["transcriber_disagreement"]:
        reason="ASR_DISAGREEMENT_HOLD"
    elif categories["other_ambiguous"]:
        reason="AMBIGUOUS_ACOUSTIC_EVIDENCE_HOLD"
    elif len(categories["repair_candidate"])>MAX_REPAIR_SLIDES:
        reason="REPAIR_CANDIDATE_BUDGET_HOLD"
    else:
        reason="BOUNDED_SAME_VOICE_REPAIR_ELIGIBLE"
    return {
        "root_cause_family":reason,
        "review_categories":categories,
        "safe_auto_repair":reason=="BOUNDED_SAME_VOICE_REPAIR_ELIGIBLE",
        "max_repair_slides":MAX_REPAIR_SLIDES,
    }


def _repair(stage:Path, report:dict, texts:list[str],
            recognizers:tuple[Callable,Callable], *,
            synthesize:Callable) -> int:
    """One candidate per *eligible* slide; never rewrite ambiguous audio."""
    from microgen_tts_provenance import wav_characteristics
    numbers=report["review_required_slides"]
    if not numbers:
        return 0
    review=_classify_review_blocker(report)
    if not review["safe_auto_repair"]:
        raise AutonomousAcousticError(
            review["root_cause_family"] +
            ": independent evidence requires bounded resolution; "
            "do not rewrite or replay original speech")
    original_manifest=verify_manifest(stage,texts)
    old_records=original_manifest["slides"]
    expected_props={(r["provider"],r["voice_name"],r["sample_rate_hz"])
                    for r in old_records}
    if len(expected_props)!=1:
        raise AutonomousAcousticError("Mixed source provider/voice/sampling")
    if old_records[0]["provider"] not in ("gemini_flash_lite_tts","gemini_flash_tts"):
        raise AutonomousAcousticError("Cannot autonomously change a non-Gemini TTS voice")
    with tempfile.TemporaryDirectory(prefix=".microgen-acoustic-retry-",
                                     dir=stage.parent) as private:
        scratch=Path(private)
        # Candidate results cannot mutate original audio before independent ASR.
        proposals={}
        for i in numbers:
            candidate=scratch/f"slide{i}.wav"
            synthesize(texts[i-1],candidate,old_records[i-1])
            if not candidate.is_file():
                raise AutonomousAcousticError("TTS retry produced no candidate WAV")
            require_structurally_usable_audio(candidate)
            if (wav_characteristics(candidate)["sample_rate_hz"]!=
                old_records[i-1]["sample_rate_hz"]):
                raise AutonomousAcousticError("Candidate audio format or voice differs")
            if not _strict_candidate(candidate,texts[i-1],recognizers):
                raise AutonomousAcousticError("TTS retry still has independently detected mismatch")
            proposals[i]=candidate
        # Build full, internally consistent candidate provenance in scratch.
        for i in range(1,len(texts)+1):
            if i not in proposals:
                shutil.copy2(stage/f"slide{i}.wav",scratch/f"slide{i}.wav")
        records=[]
        for i,record in enumerate(old_records,1):
            if i in proposals:
                record=make_record(
                    slide=i,path=scratch/f"slide{i}.wav",text=texts[i-1],
                    provider=record["provider"],key=record["key"],
                    voice_name=record["voice_name"],
                    language_code=record["language_code"],
                    speaking_rate=record["speaking_rate"],
                    location=record["location"])
            records.append(record)
        write_manifest(scratch,records,texts)
        verify_manifest(scratch,texts)
        if _input_snapshot(stage,len(texts))!=report["input_snapshot_sha256"]:
            raise AutonomousAcousticError("Inputs changed during TTS correction")
        # Preserve an immutable private backup, then replace WAV+manifest+metadata.
        backup=scratch/"original_backup"
        backup.mkdir()
        source_paths=[stage/f"slide{i}.wav" for i in numbers]
        source_paths+=[stage/".microgen_tts_cache"/f"slide{i}.json" for i in numbers]
        source_paths.append(stage/".microgen_tts_provenance.json")
        if any(p.is_symlink() for p in source_paths):
            raise AutonomousAcousticError("Unsafe TTS cache or provenance symlink")
        for i,p in enumerate(source_paths):
            if p.is_file():
                shutil.copy2(p,backup/f"{i}.original")
        changed=[]
        try:
            for i in numbers:
                dest=stage/f"slide{i}.wav"
                shutil.copy2(scratch/f"slide{i}.wav",dest)
                changed.append(dest)
                metadata=stage/".microgen_tts_cache"/f"slide{i}.json"
                metadata.parent.mkdir(exist_ok=True)
                metadata.write_text(json.dumps(records[i-1],indent=2),encoding="utf8")
                changed.append(metadata)
            target=stage/".microgen_tts_provenance.json"
            shutil.copy2(scratch/".microgen_tts_provenance.json",target)
            changed.append(target)
            verify_manifest(stage,texts)
            check_wavs(stage,len(texts))
        except Exception:
            for dest in reversed(changed):
                pos=source_paths.index(dest)
                saved=backup/f"{pos}.original"
                if saved.is_file():
                    shutil.copy2(saved,dest)
                else:
                    dest.unlink(missing_ok=True)
            raise
    return len(numbers)


def verify_receipt(stage:Path) -> dict:
    stage=Path(stage)
    path=stage/RECEIPT
    if not path.is_file() or path.is_symlink():
        raise AutonomousAcousticError("Missing autonomous acoustic evidence")
    receipt=json.loads(path.read_text(encoding="utf8"))
    if (receipt.get("schema_version")!=1 or
        receipt.get("status")!="AUTONOMOUS_INDEPENDENT_ASR_SCREEN_PASSED" or
        receipt.get("publication_allowed") is not False or
        receipt.get("human_approval_required") is not False):
        raise AutonomousAcousticError("Invalid acoustic acceptance receipt")
    texts=_normalized(stage)
    if receipt.get("slide_count")!=len(texts):
        raise AutonomousAcousticError("Acoustic receipt slide count mismatch")
    try:
        verify_manifest(stage,texts)
        _verify(stage,receipt["independent_report"],texts)
    except Exception as exc:
        raise AutonomousAcousticError(
            "Stale or unverified acoustic provenance: "+str(exc)) from exc
    if (receipt.get("source_inputs")!={
        "script_tts_sha256":digest_file(stage/"script_tts.json"),
        "tts_provenance_sha256":digest_file(stage/".microgen_tts_provenance.json")}):
        raise AutonomousAcousticError("Source/acoustic receipt SHA drift")
    return receipt


def _hold_unchanged_failed_review(stage:Path, texts:list[str],
                                  models:tuple[str,str]) -> None:
    """Do not rebill the same failed source/WAVs under identical reviewers.

    The durable blocked receipt is evidence of an *attempt*, not evidence
    that any specific WAV is wrong. An updated raw WAV/provenance snapshot or
    different independently authorized reviewers is a materially new scope.
    This runs on the normal direct CLI as well as the batch entrypoint.
    """
    snapshot=_input_snapshot(stage,len(texts))
    for old in sorted(stage.glob(".microgen_acoustic_blocked_*.json")):
        if (old.is_symlink() or not old.is_file()
                or old.stat().st_size>128_000):
            raise AutonomousAcousticError(
                "UNVERIFIABLE_PRIOR_ACOUSTIC_REVIEW_HOLD")
        try:
            earlier=json.loads(old.read_text(encoding="utf8"))
        except (OSError,ValueError):
            # An unreadable prior record is not a license to retry paid work.
            raise AutonomousAcousticError(
                "UNVERIFIABLE_PRIOR_ACOUSTIC_REVIEW_HOLD")
        if not isinstance(earlier,dict):
            raise AutonomousAcousticError(
                "UNVERIFIABLE_PRIOR_ACOUSTIC_REVIEW_HOLD")
        if (earlier.get("status")=="INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED"
            and earlier.get("input_snapshot_sha256")==snapshot
            and earlier.get("recognition_models")==list(models)):
            raise AutonomousAcousticError(
                "UNCHANGED_ACOUSTIC_REVIEW_HOLD: source and WAV inputs "
                "already received an independent blocked review with these "
                "models; no duplicate paid acoustic submission")


def audit_stage(stage:Path, *, engines:tuple[Callable,Callable]|None=None,
                models:tuple[str,str]|None=None,
                synthesize:Callable|None=None) -> dict:
    stage=Path(stage)
    if (stage/RECEIPT).exists():
        return verify_receipt(stage)
    texts=_normalized(stage)
    try:
        verify_manifest(stage,texts)
    except TTSProvenanceError as exc:
        # Diagnose normalizer changes BEFORE any new paid ASR request. The
        # original WAVs remain immutable; this report is an actionable
        # source/voice-pinned re-render inventory, not acoustic clearance.
        try:
            drift=inspect_normalized_input_drift(stage,texts)
        except TTSProvenanceError as corrupt:
            raise AutonomousAcousticError(
                "UNVERIFIED_AUDIO_PROVENANCE_HOLD: cannot trust original WAV "
                "identity or isolate source input drift") from corrupt
        if drift["changed_input_slides"]:
            raise AutonomousAcousticError(
                "SOURCE_NORMALIZER_DRIFT_HOLD: re-render source-changed "
                f"slides {drift['changed_input_slides']} in the previously "
                "pinned voice and re-run independent acoustic QA within a "
                "new valid finite campaign; old WAVs preserved") from exc
        raise AutonomousAcousticError(
            "UNVERIFIED_AUDIO_PROVENANCE_HOLD: historical manifest differs "
            "despite unchanged normalized inputs") from exc
    check_wavs(stage,len(texts))
    from microgen_tts_wave_integrity import analyze_pcm
    for n in range(1,len(texts)+1):
        evidence=analyze_pcm(stage/f"slide{n}.wav")
        if evidence["blocking_defects"]:
            raise AutonomousAcousticError(
                f"Slide {n} PCM defects block independent ASR: "
                +", ".join(evidence["blocking_defects"]))
    if engines is None:
        first,second,found=_providers()
        engines=(first,second)
        models=found
    if models is None:
        models=DEFAULT_MODELS
    if (len(engines)!=2 or len(models)!=2 or
        not all(models) or models[0]==models[1]):
        raise AutonomousAcousticError("Distinct independent Gemini recognizers required")
    # Normal CLI and batch both consult the immutable historical failure
    # BEFORE the first billable recognition request.
    _hold_unchanged_failed_review(stage,texts,models)
    memo={}
    report=_transcripts(stage,texts,engines,models,memo=memo)
    report=_recheck_disagreements(stage,report,texts,engines,models,memo)
    correction_count=0
    try:
        # Provider outages are not pronunciation defects. Never spend the
        # local two-slide audio-repair budget on missing ASR transcripts.
        if report.get("unavailable_recognizer_passes"):
            raise AutonomousAcousticError(
                "Independent acoustic transcription unavailable for model "
                "pass(es) "+str(report["unavailable_recognizer_passes"]))
        if report["review_required_slides"]:
            correction_count=_repair(
                stage,report,texts,engines,
                synthesize=synthesize or _render_same_voice)
            report=_transcripts(stage,texts,engines,models,memo=memo)
        _verify(stage,report,texts)
        receipt={
            "schema_version":1,
            "status":"AUTONOMOUS_INDEPENDENT_ASR_SCREEN_PASSED",
            "slide_count":len(texts),
            "recognition_models":list(models),
            "repaired_audio_slides":correction_count,
            "source_inputs":{
                "script_tts_sha256":digest_file(stage/"script_tts.json"),
                "tts_provenance_sha256":digest_file(stage/".microgen_tts_provenance.json")},
            "independent_report":report,
            "automatic_technical_review":True,
            "human_approval_required":False,
            "pronunciation_perfection_certified":False,
            "publication_allowed":False,
        }
        path=stage/RECEIPT
        with path.open("x",encoding="utf8") as f:
            f.write(json.dumps(receipt,indent=2,ensure_ascii=False))
        verify_receipt(stage)
        return receipt
    except Exception as exc:
        # Preserve a source/WAV-bound local diagnostic; never forge a pass.
        snap=_input_snapshot(stage,len(texts))
        signature=hashlib.sha256(json.dumps(snap,sort_keys=True).encode()).hexdigest()[:16]
        # A stable input SHA alone is NOT a unique audit attempt: new model
        # transcripts and improved QA code must never be hidden behind an old
        # blocked diagnostic. Keep every bounded failure as its own receipt.
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        failed=stage/f".microgen_acoustic_blocked_{signature}_{stamp}.json"
        rows=report.get("slides",[])
        classification=_classify_review_blocker(report)
        # Prior terminal acoustic reviews recorded only counts, losing the
        # original model-blind disagreement and forcing new billed requests.
        # Keep a bounded SHA-bound PRIVATE trace on owner-authorized HP only;
        # never send to Git, source folders or publication outputs.
        from microgen_private_acoustic_trace import (
            retain_private_failed_acoustic_review,
        )
        private_trace_retained = retain_private_failed_acoustic_review(
            stage, texts, report, models)
        diagnostic={
            "status":"INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED",
            # Stable, sanitized, automated recurrence classification.
            # Do not log the expected script or blind ASR transcripts.
            "root_cause_family":classification["root_cause_family"],
            "review_categories":classification["review_categories"],
            "safe_auto_repair":classification["safe_auto_repair"],
            "max_repair_slides":MAX_REPAIR_SLIDES,
            "input_snapshot_sha256":snap,
            "audit_utc":stamp,
            "qa_code_sha256":digest_file(Path(__file__)),
            "recognition_models":list(models),
            "review_required_slides":report.get("review_required_slides",[]),
            "unavailable_recognizer_passes":
                report.get("unavailable_recognizer_passes",[]),
            # Status-only diagnostics: never expose blind ASR transcripts,
            # expected narration, credentials, or human approval claims.
            "slide_assessments":{str(row["slide"]):row["assessment"]
                                 for row in rows},
            "model_difference_fractions":{
                str(row["slide"]):[
                    m.get("difference_fraction_upper_bound") if isinstance(m,dict)
                    else None for m in row.get("comparisons",[])]
                for row in rows},
            "recognized_word_counts":{
                str(row["slide"]):[len(t.split()) for t in row.get("transcripts",[])]
                for row in rows},
            "source_pronunciation_risk_slides":[
                row["slide"] for row in rows if row.get("source_pronunciation_risks")],
            "private_blind_transcripts_retained":private_trace_retained,
            "failure_type":type(exc).__name__,
            "accepted_for_video":False,
            "human_approval_required":False,
            "publication_allowed":False,
        }
        with failed.open("x",encoding="utf8") as f:
            json.dump(diagnostic,f,indent=2)
        raise AutonomousAcousticError("Autonomous acoustic QA blocked: "+str(exc)) from exc


def main()->int:
    result=audit_stage(Path.cwd())
    print(json.dumps({
        "status":result["status"],
        "slide_count":result["slide_count"],
        "repaired_audio_slides":result["repaired_audio_slides"],
        "human_approval_required":False},ensure_ascii=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
