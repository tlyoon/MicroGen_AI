"""Assemble a real 14-slide Serway §1.1 offline neural lecture candidate.

A release block survives successful academic-topic, PCM, ASR and video checks.
No provider calls, publication, copyright upload or formal voice promotion.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from microgen_pronunciation_closed_loop import sha_file
from microgen_section_academic_coverage import audit_section_11
from microgen_expanded_neural_tts import prepare_request, verify_audio
from microgen_offline_diagnostic_av import build_demo_video

class ExpandedLectureError(ValueError):pass

def preflight(stage:Path,narration:Path,plan:Path,slides_dir:Path,
              coverage:Path,wav_dir:Path,model_dir:Path,asr:Path)->dict:
    stage,narration,plan,slides_dir,coverage,wav_dir,model_dir,asr=map(Path,
        (stage,narration,plan,slides_dir,coverage,wav_dir,model_dir,asr))
    ledger=wav_dir/"expanded_neural_qa_receipt.json"
    paths=(stage/"source.pdf",stage/"Figure 1.1.png",narration,plan,
           slides_dir/"slides_teaching_candidate.pdf",
           slides_dir/"teaching_slide_receipt.json",coverage,ledger,asr)
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ExpandedLectureError("Complete independent source/media receipts required")
    before={str(p):sha_file(p) for p in paths}
    verified=audit_section_11(stage,narration,plan,slides_dir)
    expected=prepare_request(stage,narration,slides_dir,coverage,model_dir)
    ledger_data=json.loads(ledger.read_text(encoding="utf8"))
    asr_data=json.loads(asr.read_text(encoding="utf8"))
    if (verified["slide_count"]!=14
        or verified["rendered_teaching_pdf_sha256"]!=expected["deck_sha256"]
        or verified["visual_plan_sha256"]!=sha_file(plan)
        or ledger_data.get("status")!="FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL"
        or ledger_data.get("publication_allowed") is not False
        or ledger_data.get("formal_voice_authorized") is not False
        or ledger_data.get("slide_count")!=14
        or len(ledger_data.get("slides",[]))!=14
        or ledger_data.get("academic_source_sha256")!=expected["source_pdf_sha256"]
        or ledger_data.get("academic_report_sha256")!=expected["academic_report_sha256"]
        or ledger_data.get("deck_sha256")!=expected["deck_sha256"]
        or ledger_data.get("narration_qa_sha256")!=expected["narration_qa_sha256"]
        or ledger_data.get("voice_model_sha256")!=expected["model_sha256"]
        or asr_data.get("status")!="FOURTEEN_NEURAL_WAV_ASR_ADVISORY"
        or asr_data.get("slide_count")!=14
        or len(asr_data.get("slides",[]))!=14
        or asr_data.get("audio_receipt_sha256")!=sha_file(ledger)
        or asr_data.get("narration_sha256")!=sha_file(narration)
        or asr_data.get("formal_voice_authorized") is not False
        or asr_data.get("publication_allowed") is not False
        or asr_data.get("all_phonemes_independently_verified") is not False
        or asr_data.get("targeted_hazard_count")!=0):
        raise ExpandedLectureError("Candidate academic, audio, voice or ASR identity changed")
    actual=verify_audio(wav_dir,expected)
    if abs(actual["total_seconds"]-ledger_data["total_seconds"])>.015:
        raise ExpandedLectureError("WAVs do not match original source ledger")
    if len(asr_data["slides"])!=14:
        raise ExpandedLectureError("Not all clips independently recognized")
    for i,(wav,stored,observed) in enumerate(zip(
            actual["slides"],ledger_data["slides"],asr_data["slides"]),1):
        if (wav["slide"]!=i or stored.get("slide")!=i or observed.get("slide")!=i
            or wav["probe_wav_sha256"]!=stored.get("probe_wav_sha256")
            or wav["probe_wav_sha256"]!=observed.get("wav_sha256")
            or wav["original_text_sha256"]!=stored.get("original_text_sha256")
            or wav["synthesis_text_sha256"]!=stored.get("synthesis_text_sha256")
            or wav["topic_id"]!=stored.get("topic_id")):
            raise ExpandedLectureError(f"One of the fourteen narrated clips or ASR reports drifted: {i}")
    if any(sha_file(Path(p))!=sha for p,sha in before.items()):
        raise ExpandedLectureError("Immutable source or evidence changed during preflight")
    return {"schema_version":1,"status":"FOURTEEN_SLIDE_SOURCE_AUDIO_CANDIDATE_PREFLIGHT_PASSED",
       "source_pdf_sha256":expected["source_pdf_sha256"],
       "figure_sha256":expected["figure_sha256"],
       "deck_sha256":expected["deck_sha256"],
       "plan_sha256":sha_file(plan),
       "narration_sha256":expected["narration_qa_sha256"],
       "academic_report_sha256":expected["academic_report_sha256"],
       "academic_coverage_spot_check_14_of_14":True,
       "wav_receipt_sha256":sha_file(ledger),"asr_receipt_sha256":sha_file(asr),
       "voice_model_sha256":expected["model_sha256"],
       "input_wav_sha256":[p["probe_wav_sha256"] for p in actual["slides"]],
       "wav_total_seconds":actual["total_seconds"],
       "ASR_glossary_misses_advisory":asr_data["recognizer_glossary_gaps"],
       "source_content_and_voice_phonemes_comprehensively_approved":False,
       "model_weights_distribution_legally_cleared":False,
       "formal_voice_authorized":False,"publication_allowed":False}

def build_14_lecture(stage:Path,narration:Path,plan:Path,slides_dir:Path,
                     coverage:Path,wav_dir:Path,model_dir:Path,asr:Path,
                     new_dir:Path,*,ffmpeg_bin:str="ffmpeg",ffprobe_bin:str="ffprobe")->dict:
    evidence=preflight(stage,narration,plan,slides_dir,coverage,wav_dir,model_dir,asr)
    output=Path(new_dir).resolve(strict=False)
    if (output.exists() or Path(new_dir).is_symlink()
        or not output.parent.is_dir()
        or Path(wav_dir).resolve(strict=True) in output.parents
        or Path(stage).resolve(strict=True) in output.parents
        or any(k.casefold()=="my drive" for k in output.parts)):
        raise ExpandedLectureError("Require fresh private candidate output outside source/Drive")
    temporary=Path(tempfile.mkdtemp(prefix=".microgen-14-slide-lecture-",dir=output.parent))
    try:
        technical_dir=temporary/"technical_mux"
        mux=build_demo_video(
            slides_dir,narration,wav_dir,technical_dir,
            declared_diagnostic_voice="en_US-ljspeech-medium LOCAL NEURAL CANDIDATE ONLY",
            ffmpeg_bin=ffmpeg_bin,ffprobe_bin=ffprobe_bin)
        if (mux.get("status")!="DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION"
            or mux.get("slide_count")!=14
            or mux.get("all_slide_midpoints_source_pixel_checked") is not True
            or len(mux.get("video_slide_frame_alignment",[]))!=14
            or any(p.get("mean_absolute_rgb_fraction",1)>.03 for p in
                   mux["video_slide_frame_alignment"])
            or mux.get("publication_allowed") is not False
            or mux.get("formal_voice_authorized") is not False
            or abs(mux["diagnostic_mp4_duration_seconds"]
                   -evidence["wav_total_seconds"])>max(2,evidence["wav_total_seconds"]*.02)):
            raise ExpandedLectureError("One or more real 14-slide FFmpeg mux/frame gates failed")
        mp4=temporary/"lecture_14_slide_neural_candidate.mp4"
        (technical_dir/"lecture_diagnostic_only.mp4").rename(mp4)
        (technical_dir/"diagnostic_av_receipt.json").rename(
            temporary/"independent_mux_technical_report.json")
        evidence.update({"schema_version":1,
            "status":"REAL_FOURTEEN_SLIDE_NEURAL_MP4_CANDIDATE_NOT_FORMAL",
            "real_mp4_exists":True,"mp4_sha256":sha_file(mp4),
            "mp4_duration_seconds":mux["diagnostic_mp4_duration_seconds"],
            "full_slide_frame_verifications":mux["video_slide_frame_alignment"],
            "max_normalized_frame_pixel_error":max(x["mean_absolute_rgb_fraction"]
                     for x in mux["video_slide_frame_alignment"]),
            "mux_report_sha256":sha_file(temporary/"independent_mux_technical_report.json"),
            "source_coverage_not_full_academic_proof":True,
            "entire_phonetic_quality_independently_verified":False,
            "formal_voice_authorized":False,
            "model_weights_distribution_legally_cleared":False,
            "copyright_publication_permission_verified":False,
            "production_lecture_approved":False,"provider_calls":0,
            "publication_allowed":False,
            "unresolved_release_gates":[
               "formal narrator voice authorization",
               "complete acoustic/phonetic quality evidence",
               "external distribution rights for voice and textbook figures",
               "full academic statement accuracy beyond enumerated spot checks"]})
        (temporary/"lecture_14_candidate_receipt.json").write_text(
            json.dumps(evidence,indent=2),encoding="utf8")
        shutil.rmtree(technical_dir)
        if sha_file(mp4)!=evidence["mp4_sha256"]:
            raise ExpandedLectureError("Video changed after independent mux")
        if output.exists():raise ExpandedLectureError("Video candidate output race")
        os.rename(temporary,output)
        return evidence
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def main(argv=None):
    p=argparse.ArgumentParser()
    for k in ("stage","narration","plan","slides-dir","coverage",
              "wav-dir","model-dir","asr","new-dir"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args(argv)
    output=build_14_lecture(a.stage,a.narration,a.plan,a.slides_dir,
        a.coverage,a.wav_dir,a.model_dir,a.asr,a.new_dir)
    print(json.dumps({"status":output["status"],"slides":14,
       "mp4_seconds":output["mp4_duration_seconds"],
       "frame_matches":len(output["full_slide_frame_verifications"]),
       "publication_allowed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
