"""Unattended, non-publishing MicroGen TTS acoustic + QA campaign.

No human gates. No invented model predictions. Exact source WAV/manifest SHA
checks, genuine independent recognition, and the normal autonomous technical
release audit determine technical readiness. This is NOT a publisher.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

from microgen_tts_acoustic_qa import audit_with_recognizer,gemini_audio_recognizer
from microgen_tts_quality_campaign import run_qa_campaign
from microgen_tts_release_audit import audit_stage
from microgen_tts_recognition_budget import plan_recognition
from microgen_tts_model_calibration import check_model_calibration
from microgen_tts_targeted_phoneme import scan_stage
from microgen_tts_phoneme_evidence import verify_scan
from microgen_tts_blind_phoneme import gemini_phoneme_judge
from text_to_speech_v25 import normalize_scientific_speech

class AutonomousCampaignError(ValueError):
    pass


def preflight_before_paid_recognition(stage:Path,new_output:Path,*,
                                     max_audio_seconds:float=1200.,
                                     max_requests:int=120,
                                     multipart_receipt:Path|None=None,
                                     independent_av_receipt:Path|None=None)->dict:
    """Require every non-ASR technical gate BEFORE transcribing any WAV."""
    stage=Path(stage).resolve(strict=True)
    new_output=Path(new_output).resolve(strict=False)
    if (new_output==stage or stage in new_output.parents or
        new_output in stage.parents or new_output.exists() or new_output.is_symlink()):
        raise AutonomousCampaignError("Fresh external output folder required")
    report=audit_stage(stage, multipart_receipt=multipart_receipt,
                       independent_av_receipt=independent_av_receipt)
    blockers=[name for name in report["technical_blockers"]
              if name!="independent_acoustic_screen"]
    if blockers:
        raise AutonomousCampaignError(
            "Prepaid technical preflight failed: "+", ".join(blockers))
    budget=plan_recognition(stage,report["slide_count"],
                            max_audio_seconds=max_audio_seconds,
                            max_requests=max_requests)
    return {
        "resource_budget":budget,
        "slide_count":report["slide_count"],
        "video_duration_seconds":report["video_duration_seconds"],
        "verified_wav_sha256":report["wav_sha256"],
        "verified_video_sha256":report["video_sha256"],
        "prepaid_checks_passed":True,
        "manual_review_required":False,
    }


def continue_media_without_paid_recognition(
    stage:Path, new_output:Path, *,
    multipart_receipt:Path|None=None,
    independent_av_receipt:Path|None=None,
)->dict:
    """Perform a real, read-only source/WAV/video QA continuation without ASR.

    The workflow can resume editing/rendering with advisories, but this is
    NEVER independent phonetic evidence or a publication approval.
    """
    source=Path(stage).resolve(strict=True)
    dest=Path(new_output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest==source or
            source in dest.parents or dest in source.parents):
        raise AutonomousCampaignError("Fresh independent QA destination required")
    if (multipart_receipt is None) != (independent_av_receipt is None):
        raise AutonomousCampaignError("Both independent multipart receipts required")
    preview=audit_stage(source,multipart_receipt=multipart_receipt,
                        independent_av_receipt=independent_av_receipt)
    decision=preview["audio_generation_progression"]
    if not decision["can_continue_media_generation"]:
        raise AutonomousCampaignError("Critical WAV, source or voice defect; no continued media generation")
    result=run_qa_campaign(
        source,dest,multipart_receipt=multipart_receipt,
        independent_av_receipt=independent_av_receipt)
    progression=result["audio_generation_progression"]
    if not progression["can_continue_media_generation"]:
        raise AutonomousCampaignError("Source changed during QA; reject progression")
    return {
        "schema_version":1, "execution_mode":"OFFLINE_NO_ASR_NO_TTS_BILLING",
        "audio_generation_progression":progression,
        "slide_count":result["slide_count"],
        "source_risks":result["risk_count"],
        "listening_clips":result["review_clips"],
        "video_technical_av":(
            result["multipart_delivery_evidence"]["technical_multipart_av_pass"]
            if result["multipart_delivery_evidence"] else
            preview["checks"]["video_duration_and_av_integrity"]),
        "strict_release_blockers":result["release_blockers"],
        "qa_directory":str(dest),
        "independent_phonetics_verified":False,
        "academic_content_verified":False,
        "element_level_highlights_verified":False,
        "ready_for_separate_promotion":False,
        "publication_allowed":False, "published":False,
        "original_assets_modified":False,
        "next_action":"CONTINUE_MEDIA_WORK_WITH_RECORDED_ADVISORIES",
    }


def run_autonomous_campaign(
    stage:Path, new_output:Path,
    primary:Callable[[Path],str],
    secondary:Callable[[Path],str],
    *, models:tuple[str,str]=("primary-recognizer","secondary-recognizer"),
    max_audio_seconds:float=1200.,max_requests:int=120,
    calibration_bundle:tuple[dict,dict,Path]|None=None,
    require_calibration:bool=False,
    phonetic_reference:tuple[dict,Path]|None=None,
    phonetic_judges:tuple[Callable,Callable]|None=None,
    require_calibrated_phoneme:bool=False,
    multipart_receipt:Path|None=None,
    independent_av_receipt:Path|None=None,
)->dict:
    """Complete independent acoustic screen and immutable review packet.

    Recognition operates on the untouched original stage. If a model fails,
    the resulting evidence is marked unavailable and release remains blocked.
    """
    stage=Path(stage).resolve(strict=True)
    new_output=Path(new_output).resolve(strict=False)
    if (new_output==stage or stage in new_output.parents or
        new_output in stage.parents or new_output.exists() or new_output.is_symlink()):
        raise AutonomousCampaignError("Fresh external output folder required")
    preflight=preflight_before_paid_recognition(
        stage,new_output,max_audio_seconds=max_audio_seconds,
        max_requests=max_requests,multipart_receipt=multipart_receipt,
        independent_av_receipt=independent_av_receipt)
    if require_calibration and calibration_bundle is None:
        raise AutonomousCampaignError("Strict model calibration required before paid recognition")
    calibration_status="MODEL_CALIBRATION_NOT_PROVIDED"
    calibration=None
    if calibration_bundle is not None:
        manifest,report,benchmark_wavs=calibration_bundle
        calibration=check_model_calibration(
            manifest,report,Path(benchmark_wavs),expected_models=models)
        if not calibration["qualified_for_tested_risk_family"]:
            raise AutonomousCampaignError("Model pair failed known Y-pronunciation calibration")
        calibration_status="QUALIFIED_FOR_TESTED_Y_PRONUNCIATION_ONLY"
    if require_calibrated_phoneme and (phonetic_reference is None or phonetic_judges is None):
        raise AutonomousCampaignError("Strict phonetic check requires real reference WAVs and two judges")
    phonetic_report=None
    phonetic_verdict=None
    if require_calibrated_phoneme:
        reference,ref_dir=phonetic_reference
        phonetic_report=scan_stage(stage,reference,ref_dir,
            phonetic_judges[0],phonetic_judges[1],models=models)
        phonetic_verdict=verify_scan(stage,reference,ref_dir,phonetic_report)
        if not phonetic_verdict["technically_cleared"]:
            raise AutonomousCampaignError("Phonetic calibration or tested Y-value check failed; no full-lecture ASR")
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if (not slides or
        [item.get("slide") for item in slides]!=list(range(1,len(slides)+1))):
        raise AutonomousCampaignError("Invalid narration slide mapping")
    source=[str(item.get("tts_text") or item.get("narration") or "") for item in slides]
    acoustic=audit_with_recognizer(
        stage,source,primary,normalize_scientific_speech,
        independent_recognizer=secondary,recognition_models=models)
    campaign=run_qa_campaign(stage,new_output,acoustic_report=acoustic,
        multipart_receipt=multipart_receipt,
        independent_av_receipt=independent_av_receipt)
    if phonetic_report is not None:
        with (new_output/"calibrated_phonetic_evidence.json").open("x",encoding="utf8") as output:
            output.write(json.dumps(phonetic_report,ensure_ascii=False,indent=2)+"\n")
    result={
        "schema_version":1,
        "prepaid_preflight":preflight,
        "model_calibration_status":calibration_status,
        "calibration_evidence":calibration,
        "strict_phonetic_probe_enabled":require_calibrated_phoneme,
        "narrow_phonetic_verification":phonetic_verdict,
        "qa_directory":str(new_output),
        "slide_count":campaign["slide_count"],
        "models":list(models),
        "independent_acoustic_evidence_verified":campaign["acoustic_evidence_verified"],
        "automated_technical_qa_passed":campaign["automated_technical_qa_passed"],
        "ready_for_separate_promotion":campaign["release_ready"],
        "blocking_checks":campaign["release_blockers"],
        "human_approval_required":False,
        "human_review_completed":False,
        "published":False,
        "original_assets_modified":False,
        "note":"Unattended technical screening is not phonetic or academic certification.",
    }
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(
        description="One-command independent TTS acoustic and QA campaign (no publication)")
    parser.add_argument("isolated_lecture",type=Path)
    parser.add_argument("new_external_qa_folder",type=Path)
    parser.add_argument("--primary-model",default="gemini-3.5-flash")
    parser.add_argument("--secondary-model",default="gemini-3.8-flash")
    parser.add_argument("--max-input-audio-seconds",type=float,default=1200.)
    parser.add_argument("--max-recognition-requests",type=int,default=120)
    parser.add_argument("--require-calibration",action="store_true",
                        help="Strict machine calibration against real labeled audio; no manual gate")
    parser.add_argument("--calibration-manifest",type=Path)
    parser.add_argument("--calibration-report",type=Path)
    parser.add_argument("--calibration-audio",type=Path)
    parser.add_argument("--require-calibrated-phoneme",action="store_true",
                        help="Optional machine-only check of tested Y-value sounds")
    parser.add_argument("--phoneme-manifest",type=Path)
    parser.add_argument("--phoneme-audio-dir",type=Path)
    parser.add_argument("--offline",action="store_true",
                        help="No network; produces blocked UNKNOWN diagnostics, not fake passes")
    parser.add_argument("--continue-without-asr",action="store_true",
                        help="Resume media workflow without recognition, billing or release approval")
    parser.add_argument("--multipart-receipt",type=Path,
                        help="Original external multipart AV delivery receipt")
    parser.add_argument("--multipart-independent-av",type=Path,
                        help="External independently decoded multipart AV receipt")
    args=parser.parse_args(argv)
    if args.primary_model==args.secondary_model:
        parser.error("Two distinct independent recognizers required")
    stage=args.isolated_lecture.resolve(strict=True)
    output=args.new_external_qa_folder.resolve(strict=False)
    if (output==stage or stage in output.parents or output in stage.parents
        or output.exists() or output.is_symlink()):
        parser.error("Output must be a new directory outside the lecture source")
    if args.continue_without_asr:
        if (args.require_calibration or args.require_calibrated_phoneme or
                args.calibration_manifest or args.calibration_report or
                args.calibration_audio or args.phoneme_manifest or args.phoneme_audio_dir):
            parser.error("No recognizer/calibration option can certify offline continuation")
        result=continue_media_without_paid_recognition(
            stage,output,multipart_receipt=args.multipart_receipt,
            independent_av_receipt=args.multipart_independent_av)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    preflight_before_paid_recognition(stage,output,
        max_audio_seconds=args.max_input_audio_seconds,
        max_requests=args.max_recognition_requests,
        multipart_receipt=args.multipart_receipt,
        independent_av_receipt=args.multipart_independent_av)
    calibration_args=(args.calibration_manifest,args.calibration_report,args.calibration_audio)
    if any(x is not None for x in calibration_args) and not all(x is not None for x in calibration_args):
        parser.error("Calibration manifest, report, and audio folder must be supplied together")
    if args.require_calibration and not all(x is not None for x in calibration_args):
        parser.error("Strict calibration requires all three calibration inputs")
    calibration_bundle=(json.loads(args.calibration_manifest.read_text(encoding="utf8")),
                        json.loads(args.calibration_report.read_text(encoding="utf8")),
                        args.calibration_audio) if all(x is not None for x in calibration_args) else None
    if calibration_bundle is not None:
        verdict=check_model_calibration(*calibration_bundle,
                       expected_models=(args.primary_model,args.secondary_model))
        if not verdict["qualified_for_tested_risk_family"]:
            raise AutonomousCampaignError("Model pair failed known Y-pronunciation calibration")
    if args.require_calibrated_phoneme and not (args.phoneme_manifest and args.phoneme_audio_dir):
        parser.error("Strict phonetic scan needs reference manifest and WAV folder")
    phoneme_reference=(json.loads(args.phoneme_manifest.read_text(encoding="utf8")),
                        args.phoneme_audio_dir) if args.require_calibrated_phoneme else None
    if args.offline:
        def unavailable(_):
            raise AutonomousCampaignError("Offline mode has no audio recognizer")
        first=second=unavailable
        phonetic_judges=(lambda *_:"UNKNOWN",lambda *_:"UNKNOWN") if args.require_calibrated_phoneme else None
    else:
        from dotenv import load_dotenv
        from gemini_keys import get_gemini_api_keys
        path=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Microvid"/".env"
        load_dotenv(path,override=False)
        keys=get_gemini_api_keys()
        if not keys:
            raise AutonomousCampaignError("No configured audio recognition credentials")
        first=gemini_audio_recognizer(keys[0],model=args.primary_model)
        second=gemini_audio_recognizer(keys[0],model=args.secondary_model)
        phonetic_judges=(gemini_phoneme_judge(keys[0],model=args.primary_model),
                          gemini_phoneme_judge(keys[0],model=args.secondary_model)) if args.require_calibrated_phoneme else None
    result=run_autonomous_campaign(stage,output,first,second,
              models=(args.primary_model,args.secondary_model),
              max_audio_seconds=args.max_input_audio_seconds,
              max_requests=args.max_recognition_requests,
              calibration_bundle=calibration_bundle,
              require_calibration=args.require_calibration,
              phonetic_reference=phoneme_reference,
              phonetic_judges=phonetic_judges,
              require_calibrated_phoneme=args.require_calibrated_phoneme,
              multipart_receipt=args.multipart_receipt,
              independent_av_receipt=args.multipart_independent_av)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if result["ready_for_separate_promotion"] else 2

if __name__=="__main__":
    raise SystemExit(main())
