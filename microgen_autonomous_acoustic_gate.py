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
from typing import Callable

from microgen_tts_acoustic_qa import (
    AcousticQAError, audit_with_recognizer, mismatch_details,
    gemini_audio_recognizer, _input_snapshot,
)
from microgen_tts_evidence import verify_acoustic_evidence
from microgen_tts_provenance import (
    verify_manifest, write_manifest, make_record, digest_file,
)
from microgen_tts_wave_integrity import require_structurally_usable_audio
from microgen_quality import check_wavs, QualityError

RECEIPT=".microgen_autonomous_acoustic_qa.json"
MAX_REPAIR_SLIDES=2
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
    return (gemini_audio_recognizer(keys[index],model=models[0]),
            gemini_audio_recognizer(keys[index],model=models[1]),models)


def _transcripts(stage: Path, texts: list[str], engines: tuple[Callable,Callable],
                 models: tuple[str,str], *, memo:dict) -> dict:
    def caching(index:int):
        def run(path:Path):
            key=(index,digest_file(path))
            if key not in memo:
                memo[key]=engines[index](path)
            return memo[key]
        return run
    from text_to_speech_v25 import normalize_scientific_speech
    return audit_with_recognizer(
        stage,texts,caching(0),normalize_scientific_speech,
        independent_recognizer=caching(1),recognition_models=models)


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


def _repair(stage:Path, report:dict, texts:list[str],
            recognizers:tuple[Callable,Callable], *,
            synthesize:Callable) -> int:
    """One candidate per affected slide; no mixed providers, no silent overwrites."""
    from microgen_tts_provenance import wav_characteristics
    numbers=report["review_required_slides"]
    if not numbers:
        return 0
    if len(numbers)>MAX_REPAIR_SLIDES:
        raise AutonomousAcousticError("Acoustic errors exceed bounded local repair budget")
    if any(report["slides"][i-1]["assessment"]!=REPAIRABLE or
           report["slides"][i-1]["source_pronunciation_risks"]
           for i in numbers):
        raise AutonomousAcousticError("Unsafe or ambiguous acoustic error: no automatic rewrite")
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


def audit_stage(stage:Path, *, engines:tuple[Callable,Callable]|None=None,
                models:tuple[str,str]|None=None,
                synthesize:Callable|None=None) -> dict:
    stage=Path(stage)
    if (stage/RECEIPT).exists():
        return verify_receipt(stage)
    texts=_normalized(stage)
    verify_manifest(stage,texts)
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
    memo={}
    report=_transcripts(stage,texts,engines,models,memo=memo)
    correction_count=0
    try:
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
        failed=stage/f".microgen_acoustic_blocked_{signature}.json"
        if not failed.exists():
            failed.write_text(json.dumps({
                "status":"INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED",
                "input_snapshot_sha256":snap,
                "review_required_slides":report.get("review_required_slides",[]),
                "failure_type":type(exc).__name__,
                "accepted_for_video":False,
                "human_approval_required":False,
                "publication_allowed":False},indent=2),encoding="utf8")
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
