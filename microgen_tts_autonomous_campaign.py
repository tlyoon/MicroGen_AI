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
from text_to_speech_v25 import normalize_scientific_speech

class AutonomousCampaignError(ValueError):
    pass

def run_autonomous_campaign(
    stage:Path, new_output:Path,
    primary:Callable[[Path],str],
    secondary:Callable[[Path],str],
    *, models:tuple[str,str]=("primary-recognizer","secondary-recognizer")
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
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if (not slides or
        [item.get("slide") for item in slides]!=list(range(1,len(slides)+1))):
        raise AutonomousCampaignError("Invalid narration slide mapping")
    source=[str(item.get("tts_text") or item.get("narration") or "") for item in slides]
    acoustic=audit_with_recognizer(
        stage,source,primary,normalize_scientific_speech,
        independent_recognizer=secondary,recognition_models=models)
    campaign=run_qa_campaign(stage,new_output,acoustic_report=acoustic)
    result={
        "schema_version":1,
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
    parser.add_argument("--offline",action="store_true",
                        help="No network; produces blocked UNKNOWN diagnostics, not fake passes")
    args=parser.parse_args(argv)
    if args.primary_model==args.secondary_model:
        parser.error("Two distinct independent recognizers required")
    stage=args.isolated_lecture.resolve(strict=True)
    output=args.new_external_qa_folder.resolve(strict=False)
    if (output==stage or stage in output.parents or output in stage.parents
        or output.exists() or output.is_symlink()):
        parser.error("Output must be a new directory outside the lecture source")
    if args.offline:
        def unavailable(_):
            raise AutonomousCampaignError("Offline mode has no audio recognizer")
        first=second=unavailable
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
    result=run_autonomous_campaign(stage,output,first,second,
              models=(args.primary_model,args.secondary_model))
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if result["ready_for_separate_promotion"] else 2

if __name__=="__main__":
    raise SystemExit(main())
