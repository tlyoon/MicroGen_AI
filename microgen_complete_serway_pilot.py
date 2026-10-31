"""Transactional offline source-to-14-slide neural lecture pilot.

Every stage creates an output in a fresh private staging directory.  Any
failure leaves original source inputs untouched and no published final folder.
This is an explicit Serway 1.1 pilot, not yet a chapter-general generator.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_teaching_slide_render import render_teaching_candidate
from microgen_section_academic_coverage import audit_section_11
from microgen_expanded_neural_tts import synthesize_expanded
from microgen_expanded_phonetic_advisory import audit_asr
from microgen_expanded_lecture_video import build_14_lecture

class CompletePilotError(ValueError):pass

def preflight_campaign(stage:Path,narration:Path,plan:Path,model_dir:Path,
                       piper_python:Path,vosk_dir:Path,ffmpeg:Path,
                       output:Path)->dict:
    stage,narration,plan,model_dir,piper_python,vosk_dir,ffmpeg,output=map(Path,
        (stage,narration,plan,model_dir,piper_python,vosk_dir,ffmpeg,output))
    dest=output.resolve(strict=False)
    source=stage/"source.pdf"
    fig=stage/"Figure 1.1.png"
    files=(source,fig,narration,plan,model_dir/"en_US-ljspeech-medium.onnx",
           model_dir/"en_US-ljspeech-medium.onnx.json",model_dir/"MODEL_CARD",
           piper_python,ffmpeg)
    if (any(not f.is_file() or f.is_symlink() for f in files)
        or not (vosk_dir/"am").is_dir()
        or model_dir.is_symlink() or vosk_dir.is_symlink()
        or output.exists() or output.is_symlink()
        or not dest.parent.is_dir()
        or stage.resolve(strict=True) in dest.parents
        or model_dir.resolve(strict=True) in dest.parents
        or any(x.casefold()=="my drive" for x in dest.parts)):
        raise CompletePilotError("Only complete immutable local inputs and fresh HP output allowed")
    from microgen_expanded_neural_tts import validate_model
    validate_model(model_dir)
    return {"source_pdf_sha256":sha_file(source),"figure_sha256":sha_file(fig),
       "narration_input_sha256":sha_file(narration),
       "visual_plan_sha256":sha_file(plan),
       "piper_model_sha256":sha_file(model_dir/"en_US-ljspeech-medium.onnx"),
       "cloud_provider_calls":0,"publication_allowed":False}

def run_complete_pilot(stage:Path,narration:Path,plan:Path,model_dir:Path,
                       piper_python:Path,vosk_dir:Path,ffmpeg:Path,
                       new_output:Path)->dict:
    input_receipt=preflight_campaign(stage,narration,plan,model_dir,piper_python,
                                     vosk_dir,ffmpeg,new_output)
    target=Path(new_output).resolve(strict=False)
    staging=Path(tempfile.mkdtemp(prefix=".microgen-complete-section11-",dir=target.parent))
    try:
        slides=staging/"slides"
        rendered=render_teaching_candidate(stage,narration,plan,slides,
                    figure_slide=7,historical_si_slide=6)
        if rendered["slide_count"]!=14 or rendered["publication_allowed"] is not False:
            raise CompletePilotError("Fresh original academic deck failed")
        coverage=staging/"independent_academic_coverage.json"
        report=audit_section_11(stage,narration,plan,slides)
        if not report.get("all_enumerated_section_11_concepts_present",False):
            raise CompletePilotError("Fresh 14-topic academic source audit failed")
        coverage.write_text(json.dumps(report,indent=2),encoding="utf8")
        wavs=staging/"wavs"
        audio=synthesize_expanded(stage,narration,slides,coverage,
            model_dir,piper_python,wavs)
        if audio.get("status")!="FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL":
            raise CompletePilotError("All fourteen neural WAVs required")
        advisory=staging/"independent_neural_asr.json"
        listening=audit_asr(wavs,narration,vosk_dir,ffmpeg,advisory)
        if listening.get("targeted_hazard_count")!=0:
            raise CompletePilotError("Documented, contextual pronunciation risk needs remediation")
        video_dir=staging/"video"
        video=build_14_lecture(stage,narration,plan,slides,coverage,wavs,model_dir,
               advisory,video_dir)
        if (video.get("status")!="REAL_FOURTEEN_SLIDE_NEURAL_MP4_CANDIDATE_NOT_FORMAL"
            or video.get("publication_allowed") is not False
            or not video.get("real_mp4_exists")
            or len(video.get("full_slide_frame_verifications",[]))!=14):
            raise CompletePilotError("Actual final media frames or release guards failed")
        for p,original in ((Path(stage)/"source.pdf",input_receipt["source_pdf_sha256"]),
                           (Path(stage)/"Figure 1.1.png",input_receipt["figure_sha256"]),
                           (Path(narration),input_receipt["narration_input_sha256"]),
                           (Path(plan),input_receipt["visual_plan_sha256"]),
                           (Path(model_dir)/"en_US-ljspeech-medium.onnx",
                            input_receipt["piper_model_sha256"])):
            if sha_file(p)!=original:
                raise CompletePilotError("Source or model mutated during complete campaign")
        receipt={**input_receipt,"schema_version":1,
           "status":"COMPLETE_SOURCE_TO_REAL_VIDEO_REPRODUCTION_NOT_RELEASED",
           "stages_completed":[
              "original_to_14_slide_pdf","source_bounded_14_topic_audit",
              "offline_14_neural_wav_synthesis","14_clip_pcm_check",
              "independent_offline_ASR_advisory",
              "14_slide_mp4_mux","14_midpoint_video_frame_pixel_QA"],
           "rendered_pdf_sha256":sha_file(slides/"slides_teaching_candidate.pdf"),
           "academic_coverage_sha256":sha_file(coverage),
           "wavs_receipt_sha256":sha_file(wavs/"expanded_neural_qa_receipt.json"),
           "ASR_observation_sha256":sha_file(advisory),
           "video_receipt_sha256":sha_file(video_dir/"lecture_14_candidate_receipt.json"),
           "video_sha256":sha_file(video_dir/"lecture_14_slide_neural_candidate.mp4"),
           "input_audio_seconds":audio["total_seconds"],
           "real_video_seconds":video["mp4_duration_seconds"],
           "slide_count":14,
           "all_slide_frames_technically_verified":True,
           "full_spoken_and_academic_accuracy_independently_proven":False,
           "formal_voice_authorized":False,
           "voice_and_textbook_distribution_rights_cleared":False,
           "production_ready":False,
           "publication_allowed":False}
        (staging/"complete_pilot_receipt.json").write_text(
            json.dumps(receipt,indent=2),encoding="utf8")
        if target.exists():raise CompletePilotError("Output destination race")
        os.rename(staging,target)
        return receipt
    finally:
        if staging.exists():shutil.rmtree(staging)

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("stage","narration","plan","model-dir","piper-python",
              "vosk-dir","ffmpeg","new-output"):
        p.add_argument("--"+x,required=True,type=Path)
    a=p.parse_args(argv)
    r=run_complete_pilot(a.stage,a.narration,a.plan,a.model_dir,
        a.piper_python,a.vosk_dir,a.ffmpeg,a.new_output)
    print(json.dumps({"status":r["status"],"slides":r["slide_count"],
        "audio_seconds":r["input_audio_seconds"],
        "video_seconds":r["real_video_seconds"],
        "publication_allowed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
