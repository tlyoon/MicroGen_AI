"""One-command, non-publishing MicroGen lecture TTS QA packet generator.

Combines strict read-only source/WAV validation, risk inventory, audio
integrity, listening clips, all-slide review queue and release blockers.
Creates a fresh QA destination only, never reuses or changes lecture assets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from microgen_tts_risk_register import build_risk_register,durations_from_wavs
from microgen_tts_audio_review import render_excerpts
from microgen_tts_listening_queue import prepare_listening_queue
from microgen_tts_release_audit import audit_stage
from microgen_tts_wave_integrity import analyze_pcm
from microgen_tts_provenance import digest_file
from text_to_speech_v25 import normalize_scientific_speech as normalize

class QACampaignError(RuntimeError):
    pass

def _snap(stage:Path,n:int)->dict:
    names=["script_tts.json"]+[f"slide{k}.wav" for k in range(1,n+1)]
    for extra in ("slides.pdf","slides.mp4","script.txt"):
        if (stage/extra).is_file():names.append(extra)
    return {name:digest_file(stage/name) for name in names}

def _store(path:Path,payload:dict):
    with path.open("x",encoding="utf8") as stream:
        stream.write(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")

def run_qa_campaign(stage:Path,new_output:Path,*,max_review_clips:int=80,
                    acoustic_report:dict|None=None)->dict:
    stage=Path(stage).resolve()
    new_output=Path(new_output).resolve()
    if new_output.exists() or new_output.is_symlink():
        raise QACampaignError("Existing QA output cannot be overwritten")
    if stage==new_output or stage in new_output.parents or new_output in stage.parents:
        raise QACampaignError("QA packet must be outside the source lesson tree")
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=data.get("slides",[])
    if not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise QACampaignError("Nonempty consecutive slide narration required")
    if max_review_clips<1 or max_review_clips>500:
        raise QACampaignError("Review clip cap outside safe bounds")
    snapshot=_snap(stage,len(slides))
    lengths=durations_from_wavs(stage,len(slides))
    wav_hashes=[snapshot[f"slide{k}.wav"] for k in range(1,len(slides)+1)]
    register=build_risk_register(slides,normalize,lengths,wav_sha256=wav_hashes)
    pcm=[]
    for i in range(1,len(slides)+1):
        metrics=analyze_pcm(stage/f"slide{i}.wav")
        pcm.append({"slide":i,"wav_sha256":wav_hashes[i-1],**metrics})
    release=audit_stage(stage,acoustic_report=acoustic_report)
    if _snap(stage,len(slides))!=snapshot:
        raise QACampaignError("Source SHA changed during preparation")
    # Only after all read-only validations succeed do we create the new folder.
    new_output.mkdir(parents=True,exist_ok=False)
    _store(new_output/"source_risks.json",register)
    _store(new_output/"pcm_audio_integrity.json",{
        "slides":pcm,"failed_slides":[r["slide"] for r in pcm if r["blocking_defects"]],
        "pronunciation_verified":False,
    })
    readiness_name=("release_readiness_TECHNICAL_READY.json"
                    if release["ready_for_separate_promotion"]
                    else "release_readiness_BLOCKED.json")
    _store(new_output/readiness_name,release)
    _store(new_output/"TTS_MEDIA_GENERATION_PROGRESSION.json",
           release["audio_generation_progression"])
    if acoustic_report is not None:
        _store(new_output/"input_acoustic_evidence.json",acoustic_report)
    excerpts=render_excerpts(stage,slides,register,
        new_output/"listening_clips",max_excerpts=max_review_clips)
    queue=prepare_listening_queue(stage,clip_manifest=excerpts,
                                  clip_folder=new_output/"listening_clips")
    _store(new_output/"all_slide_listening_queue.json",queue)
    if _snap(stage,len(slides))!=snapshot:
        raise QACampaignError("Source SHA changed during QA generation")
    packet={
        "schema_version":1,
        "input_stage":str(stage),
        "source_file_sha256":snapshot,
        "slide_count":len(slides),
        "risk_count":register["risk_count"],
        "review_clips":excerpts["clips_created"],
        "all_slide_review_count":queue["slide_count"],
        "structurally_bad_slides":[r["slide"] for r in pcm if r["blocking_defects"]],
        "video_seconds":release["video_duration_seconds"],
        "qa_policy":release["policy"],
        "release_blockers":release["blockers"],
        "release_ready":release["ready_for_separate_promotion"],
        "audio_generation_progression":release["audio_generation_progression"],
        "automated_technical_qa_passed":release["automated_technical_qa_passed"],
        "human_reviews_pending":release["human_reviews_pending"],
        "manual_approval_is_gate":release["manual_approval_is_gate"],
        "unproven_quality_dimensions":release["unproven_quality_dimensions"],
        "acoustic_recognition_run":False,
        "acoustic_evidence_imported":acoustic_report is not None,
        "acoustic_evidence_verified":release["checks"]["independent_acoustic_screen"],
        "human_listening_signed":False,
        "published":False,
        "no_original_files_modified":True,
        "report_files":[
            "source_risks.json","pcm_audio_integrity.json",
            readiness_name,"TTS_MEDIA_GENERATION_PROGRESSION.json",
            "listening_clips/review_clip_manifest.json",
            "all_slide_listening_queue.json",
            *(["input_acoustic_evidence.json"] if acoustic_report is not None else []),
        ],
        "notice":"Complete packet generation is NOT a publication approval or phonetic validation.",
    }
    _store(new_output/"QA_CAMPAIGN_COMPLETE_NOT_PUBLISHED.json",packet)
    return packet

def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Independent, read-only MicroGen TTS QA packet")
    p.add_argument("stage",type=Path)
    p.add_argument("new_output_dir",type=Path)
    p.add_argument("--acoustic-report",type=Path,
                   help="Existing independent acoustic evidence JSON; read only")
    a=p.parse_args(argv)
    acoustic=(json.loads(a.acoustic_report.read_text(encoding="utf8"))
              if a.acoustic_report else None)
    result=run_qa_campaign(a.stage,a.new_output_dir,acoustic_report=acoustic)
    print(json.dumps({"slides":result["slide_count"],
                      "risk_flags":result["risk_count"],
                      "listening_clips":result["review_clips"],
                      "release_blockers":result["release_blockers"],
                      "published":False},indent=2))
    return 0  # successful audit generation, NOT success of release
if __name__=="__main__":
    raise SystemExit(main())
