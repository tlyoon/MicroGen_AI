"""Make a *neural-voice lecture candidate* from 8 verified offline WAVs.

Reuses the independently pixel/timing checked offline mux implementation.
A source-grounded candidate is not a released or formally approved lecture.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_diagnostic_av import build_demo_video
from microgen_offline_neural_voice import digest_text

class NeuralVideoError(ValueError):pass

def check_candidate_video_inputs(teaching_dir:Path,narration_qa:Path,
                                  formal_handoff:Path,neural_audio_dir:Path)->dict:
    teaching_dir,narration_qa,formal_handoff,neural_audio_dir=map(Path,(
        teaching_dir,narration_qa,formal_handoff,neural_audio_dir))
    files={"pdf":teaching_dir/"slides_teaching_candidate.pdf",
        "slides":teaching_dir/"teaching_slide_receipt.json",
        "narration":narration_qa,"handoff":formal_handoff,
        "audio":neural_audio_dir/"candidate_audio_receipt.json"}
    if any(not p.is_file() or p.is_symlink() for p in files.values()):
        raise NeuralVideoError("Verified lecture source, handoff and all candidate WAV evidence required")
    sha={key:sha_file(path) for key,path in files.items()}
    s=json.loads(files["slides"].read_text(encoding="utf8"))
    n=json.loads(files["narration"].read_text(encoding="utf8"))
    h=json.loads(files["handoff"].read_text(encoding="utf8"))
    a=json.loads(files["audio"].read_text(encoding="utf8"))
    if (s.get("status")!="FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
        or s.get("rendered_pdf_sha256")!=sha["pdf"]
        or s.get("narration_qa_sha256")!=sha["narration"]
        or s.get("publication_allowed") is not False
        or n.get("publication_allowed") is not False
        or h.get("formal_voice_provider") is not None
        or h.get("formal_voice_name") is not None
        or h.get("formal_production_ready") is not False
        or h.get("publication_allowed") is not False
        or a.get("status")!="EIGHT_OFFLINE_NEURAL_WAV_CANDIDATES_NOT_FORMAL"
        or a.get("formal_handoff_sha256")!=sha["handoff"]
        or a.get("formal_voice_authorized") is not False
        or a.get("publication_allowed") is not False
        or a.get("slide_count")!=8 or h.get("slide_count")!=8
        or n.get("slide_count")!=8 or s.get("slide_count")!=8
        or len(a.get("slides",[]))!=8 or len(h.get("requests",[]))!=8
        or len(n.get("slides",[]))!=8 or len(s.get("slides",[]))!=8):
        raise NeuralVideoError("Refusing wrong voice, forged production or mismatched source chain")
    total=0.
    for i,(row,order,spoken,slide) in enumerate(zip(
            a["slides"],h["requests"],n["slides"],s["slides"]),1):
        filename=f"slide{i:02d}.wav"
        wav=neural_audio_dir/filename
        if (row.get("slide")!=i or order.get("slide")!=i
            or spoken.get("slide")!=i or slide.get("slide")!=i
            or row.get("wav_filename")!=filename
            or wav.is_symlink() or not wav.is_file()
            or sha_file(wav)!=row.get("probe_wav_sha256")
            or row.get("text_sha256")!=order.get("text_sha256")
            or row.get("text_sha256")!=spoken.get("spoken_text_sha256")
            or row.get("source_pdf_sha256")!=s.get("source_pdf_sha256")
            or row.get("teaching_pdf_sha256")!=sha["pdf"]
            or digest_text(order.get("input_text",""))!=row.get("text_sha256")
            or slide.get("narration_sha256")!=row.get("text_sha256")
            or row.get("local_candidate_not_formal") is not True
            or row.get("pronunciation_acoustically_verified") is not False
            or not isinstance(row.get("seconds"),(float,int))
            or not 20<=row["seconds"]<=240):
            raise NeuralVideoError(f"Neural narration clip {i} is not independently source-bound")
        total+=row["seconds"]
    if abs(total-a["total_duration_seconds"])>1:
        raise NeuralVideoError("Candidate WAV total duration ledger invalid")
    return {"original_source_pdf_sha256":s["source_pdf_sha256"],
        "teaching_pdf_sha256":sha["pdf"],
        "narration_qa_sha256":sha["narration"],
        "formal_handoff_sha256":sha["handoff"],
        "neural_wav_receipt_sha256":sha["audio"],
        "voice_model_sha256":a["model_sha256"],
        "voice_model_name":a["model_name"],
        "slide_count":8,"total_audio_seconds":round(total,3),
        "formal_voice_authorized":False,"publication_allowed":False}

def compose_neural_candidate(teaching_dir:Path,narration_qa:Path,formal_handoff:Path,
                             neural_audio_dir:Path,new_dir:Path,
                             *,ffmpeg_bin:str="ffmpeg",ffprobe_bin:str="ffprobe")->dict:
    base=check_candidate_video_inputs(teaching_dir,narration_qa,formal_handoff,neural_audio_dir)
    dest=Path(new_dir).resolve(strict=False)
    if (dest.exists() or Path(new_dir).is_symlink()
        or not dest.parent.is_dir()
        or Path(neural_audio_dir).resolve(strict=True) in dest.parents
        or Path(teaching_dir).resolve(strict=True) in dest.parents
        or any(x.casefold()=="my drive" for x in dest.parts)):
        raise NeuralVideoError("Fresh external nonpublication video candidate required")
    staging=Path(tempfile.mkdtemp(prefix=".microgen-neural-video-",dir=dest.parent))
    try:
        mux=staging/"technical_mux"
        technical=build_demo_video(
            teaching_dir,narration_qa,neural_audio_dir,mux,
            declared_diagnostic_voice=base["voice_model_name"]+" LOCAL CANDIDATE NOT FORMAL",
            ffmpeg_bin=ffmpeg_bin,ffprobe_bin=ffprobe_bin)
        if (technical.get("status")!="DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION"
            or technical.get("slide_count")!=8
            or technical.get("publication_allowed") is not False
            or technical.get("formal_voice_authorized") is not False
            or technical.get("all_slide_midpoints_source_pixel_checked") is not True
            or len(technical.get("video_slide_frame_alignment",[]))!=8):
            raise NeuralVideoError("Independent offline video/audio/slide mux technical gates failed")
        video=staging/"lecture_neural_voice_candidate.mp4"
        (mux/"lecture_diagnostic_only.mp4").rename(video)
        receipt=mux/"diagnostic_av_receipt.json"
        receipt.rename(staging/"technical_mux_evidence.json")
        record={**base,"schema_version":1,
            "status":"REAL_NEURAL_LECTURE_VIDEO_CANDIDATE_NOT_FORMAL",
            "mp4_sha256":sha_file(video),
            "mp4_duration_seconds":technical["diagnostic_mp4_duration_seconds"],
            "actual_video_frame_checks":technical["video_slide_frame_alignment"],
            "technical_mux_evidence_sha256":sha_file(staging/"technical_mux_evidence.json"),
            "neural_audio_and_video_actually_generated":True,
            "acoustic_technical_terms_independently_verified":False,
            "independent_academic_publication_acceptance":False,
            "production_wavs_claimed":False,"formal_voice_authorized":False,
            "cloud_provider_calls":0,"publication_allowed":False}
        (staging/"neural_video_candidate_receipt.json").write_text(
            json.dumps(record,indent=2),encoding="utf8")
        if any(sha_file(Path(neural_audio_dir)/f"slide{i:02d}.wav") != (
            json.loads((Path(neural_audio_dir)/"candidate_audio_receipt.json").read_text(
                encoding="utf8"))["slides"][i-1]["probe_wav_sha256"])
               for i in range(1,9)):
            raise NeuralVideoError("Narration WAV altered during mux")
        shutil.rmtree(mux)
        if dest.exists():raise NeuralVideoError("Destination appeared during video")
        os.rename(staging,dest)
        return record
    finally:
        if staging.exists():shutil.rmtree(staging)

def main(argv=None):
    a=argparse.ArgumentParser()
    for k in ("teaching-dir","narration-qa","formal-handoff","neural-audio-dir","new-dir"):
        a.add_argument("--"+k,required=True,type=Path)
    v=a.parse_args(argv)
    r=compose_neural_candidate(v.teaching_dir,v.narration_qa,v.formal_handoff,
                               v.neural_audio_dir,v.new_dir)
    print(json.dumps({"status":r["status"],"duration":r["mp4_duration_seconds"],
                      "slides":r["slide_count"],"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
