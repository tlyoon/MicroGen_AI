"""Portable source-manifest -> slides -> offline speech -> video candidate.

This is a production-*blocked* private demonstration. User-provided coverage
contracts are not scientifically certified full curriculum reconstructions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import audit_portable_contract
from microgen_portable_slide_render import render_portable_slides,checked_figures
from microgen_expanded_neural_tts import prepare_spoken_text,validate_model
from microgen_offline_neural_voice import MODEL_BASENAME,inspect_voice_probe
from microgen_offline_diagnostic_av import build_demo_video

class PortablePipelineError(ValueError):pass

def synthesize_portable(narration:Path,slides:Path,contract:Path,
                       model_dir:Path,python:Path,output:Path)->dict:
    narration,slides,contract,model_dir,python,output=map(
        Path,(narration,slides,contract,model_dir,python,output))
    voice=validate_model(model_dir)
    deck=slides/"slides_teaching_candidate.pdf"
    slides_receipt=slides/"teaching_slide_receipt.json"
    source=json.loads(narration.read_text(encoding="utf8"))
    m=json.loads(contract.read_text(encoding="utf8"))
    receipt=json.loads(slides_receipt.read_text(encoding="utf8"))
    count=len(m["topics"])
    if (receipt.get("status")!="PORTABLE_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
        or receipt.get("portable_contract_sha256")!=sha_file(contract)
        or receipt.get("narration_qa_sha256")!=sha_file(narration)
        or receipt.get("rendered_pdf_sha256")!=sha_file(deck)
        or receipt.get("slide_count")!=count
        or not 2<=count<=20 or len(source.get("slides",[]))!=count
        or receipt.get("formal_voice_authorized") is not False
        or receipt.get("publication_allowed") is not False
        or source.get("publication_allowed") is not False
        or not python.is_file() or python.is_symlink()):
        raise PortablePipelineError("Source or real deck is not portable and immutable")
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
        or any(p.casefold()=="my drive" for p in output.parts)):
        raise PortablePipelineError("Output must be fresh and private")
    requests=[]
    for i,row in enumerate(source["slides"],1):
        txt=row.get("narration")
        if (row.get("slide")!=i or not isinstance(txt,str)
            or row.get("topic_id")!=m["topics"][i-1]["topic_id"]
            or row.get("source_page")!=m["topics"][i-1]["source_page"]
            or hashlib.sha256(txt.encode()).hexdigest()!=row.get("spoken_text_sha256")
            or receipt["slides"][i-1]["narration_sha256"]!=row["spoken_text_sha256"]):
            raise PortablePipelineError("Invalid source speech alignment")
        spoken,lexical=prepare_spoken_text(txt)
        requests.append({"slide":i,"text":spoken,
           "original_sha256":row["spoken_text_sha256"],
           "synthesis_sha256":hashlib.sha256(spoken.encode()).hexdigest(),
           "spoken_lexicon_expansions":lexical})
    tmp=Path(tempfile.mkdtemp(prefix=".microgen-portable-wav-",dir=output.parent))
    try:
        request_file=tmp/"private_tts_request.json"
        request_file.write_text(json.dumps(requests),encoding="utf8")
        program=("import sys,json,wave,pathlib;"
           "from piper import PiperVoice;"
           "v=PiperVoice.load(sys.argv[1]);"
           "rows=json.load(open(sys.argv[2],encoding='utf8'));"
           "folder=pathlib.Path(sys.argv[3]);"
           "\nfor row in rows:"
           "\n path=folder/('slide%02d.wav'%row['slide']);"
           "\n with wave.open(str(path),'wb') as out:v.synthesize_wav(row['text'],out)")
        done=subprocess.run([str(python),"-c",program,
            str(model_dir/MODEL_BASENAME),str(request_file),str(tmp)],
            capture_output=True,text=True,timeout=1200)
        if done.returncode:
            raise PortablePipelineError("Local Piper synthesis failed: "+done.stderr[-500:])
        request_file.unlink()
        rows=[]
        for row in requests:
            i=row["slide"]
            signal=inspect_voice_probe(tmp/f"slide{i:02d}.wav",min_seconds=15,max_seconds=74.5)
            rows.append({"slide":i,"wav_filename":f"slide{i:02d}.wav",
                "narration_text_sha256":row["original_sha256"],
                "synthesis_text_sha256":row["synthesis_sha256"],
                "spoken_lexicon_expansions":row["spoken_lexicon_expansions"],**signal})
        evidence={"schema_version":1,
           "status":"PORTABLE_REAL_OFFLINE_NEURAL_WAVS_NONFORMAL",
           "section_id":m["section_id"],"slide_count":count,
           "slides":rows,"voice_model_sha256":voice["model_sha256"],
           "voice_card_sha256":voice["model_card_sha256"],
           "narration_sha256":sha_file(narration),
           "slides_pdf_sha256":sha_file(deck),
           "contract_sha256":sha_file(contract),
           "total_seconds":round(sum(z["seconds"] for z in rows),3),
           "all_phonemes_verified":False,"formal_voice_authorized":False,
           "publication_allowed":False,"provider_calls":0}
        if validate_model(model_dir)["model_sha256"]!=voice["model_sha256"]:
            raise PortablePipelineError("Piper voice model changed during synthesis")
        (tmp/"portable_audio_receipt.json").write_text(json.dumps(evidence,indent=2))
        if output.exists():raise PortablePipelineError("Output race")
        os.rename(tmp,output)
        return evidence
    finally:
        if tmp.exists():shutil.rmtree(tmp)

def observe_portable_asr(audio_dir:Path,narration:Path,contract:Path,
                         vosk_dir:Path,ffmpeg:Path,out:Path)->dict:
    from vosk import Model,SetLogLevel
    from microgen_offline_vosk_capture import capture_offline_words
    audio_dir,narration,contract,vosk_dir,ffmpeg,out=map(Path,
        (audio_dir,narration,contract,vosk_dir,ffmpeg,out))
    receipt=audio_dir/"portable_audio_receipt.json"
    if (out.exists() or not out.parent.is_dir() or not (vosk_dir/"am").is_dir()
        or not ffmpeg.is_file() or receipt.is_symlink()):
        raise PortablePipelineError("Local model and new source-bound ASR report required")
    a=json.loads(receipt.read_text())
    m=json.loads(contract.read_text())
    n=json.loads(narration.read_text())
    if (a["contract_sha256"]!=sha_file(contract)
        or a["narration_sha256"]!=sha_file(narration)
        or a.get("publication_allowed") is not False):
        raise PortablePipelineError("ASR inputs are not source-bound")
    SetLogLevel(-1)
    engine=Model(str(vosk_dir))
    checked=[]
    for i,(row,source) in enumerate(zip(a["slides"],n["slides"]),1):
        wav=audio_dir/f"slide{i:02d}.wav"
        if row["probe_wav_sha256"]!=sha_file(wav):
            raise PortablePipelineError("WAV changed before independent recognition")
        recognition=capture_offline_words(wav,engine,ffmpeg)
        words={w["word"] for w in recognition["words"]}
        # ASR false negatives, accents and homophones are advisory only.
        expected=m["topics"][i-1]["required_terms"]
        missing=[term for term in expected if
                 not any(token.lower() in words for token in re.findall(r"[A-Za-z]+",term))]
        text=source["narration"]
        risks=[]
        if re.search(r"\\dot\{C\}|\bC\s+dot\b",text) and "circa" in words:
            risks.append("C_DOT_POSSIBLE_CIRCA")
        if re.search(r"\\dot\{y\}|\by\s+dot\b",text) and "yay" in words:
            risks.append("Y_DOT_POSSIBLE_YAY")
        checked.append({"slide":i,"wav_sha256":sha_file(wav),
            "recognition_word_count":len(recognition["words"]),
            "missing_keywords_advisory":missing,
            "contextual_pronunciation_risks":risks})
    result={"schema_version":1,"status":"PORTABLE_OFFLINE_ASR_ADVISORY_NOT_PHONETIC_PROOF",
        "slide_count":len(checked),"slides":checked,
        "audio_receipt_sha256":sha_file(receipt),
        "recognizer_term_misses":sum(len(x["missing_keywords_advisory"]) for x in checked),
        "targeted_pronunciation_risks":sum(len(x["contextual_pronunciation_risks"]) for x in checked),
        "full_acoustic_verification":False,"publication_allowed":False}
    with out.open("x",encoding="utf8") as stream:json.dump(result,stream,indent=2)
    return result

def run_portable_pipeline(stage:Path,narration:Path,plan:Path,contract:Path,
                          model_dir:Path,piper_python:Path,vosk_dir:Path,
                          ffmpeg:Path,new_output:Path)->dict:
    stage,narration,plan,contract,model_dir,piper_python,vosk_dir,ffmpeg,new_output=map(
        Path,(stage,narration,plan,contract,model_dir,piper_python,vosk_dir,ffmpeg,new_output))
    source=stage/"source.pdf"
    academic=audit_portable_contract(source,narration,plan,contract)
    manifest=json.loads(contract.read_text(encoding="utf8"))
    figs=checked_figures(stage,manifest,academic["topic_count"])
    guard=[source,narration,plan,contract,model_dir/MODEL_BASENAME,
           model_dir/(MODEL_BASENAME+".json"),model_dir/"MODEL_CARD"]+[p for p,_,_ in figs.values()]
    if (any(not p.is_file() or p.is_symlink() for p in guard)
        or new_output.exists() or new_output.is_symlink()
        or not new_output.parent.is_dir()
        or stage.resolve(strict=True) in new_output.resolve(strict=False).parents
        or any(p.casefold()=="my drive" for p in new_output.parts)):
        raise PortablePipelineError("Fresh private output and immutable figure/source inputs required")
    frozen={str(p):sha_file(p) for p in guard}
    staging=Path(tempfile.mkdtemp(prefix=".microgen-portable-campaign-",dir=new_output.parent))
    try:
        academic_file=staging/"independent_portable_academic_coverage.json"
        academic_file.write_text(json.dumps(academic,indent=2),encoding="utf8")
        slide_dir=staging/"slides"
        visual=render_portable_slides(stage,narration,plan,contract,slide_dir)
        audio_dir=staging/"audio"
        audio=synthesize_portable(narration,slide_dir,contract,model_dir,piper_python,audio_dir)
        observed_path=staging/"portable_asr_advisory.json"
        heard=observe_portable_asr(audio_dir,narration,contract,vosk_dir,ffmpeg,observed_path)
        if heard["targeted_pronunciation_risks"]>0:
            raise PortablePipelineError("Targeted pronunciation risk requires a bounded diagnostic correction")
        mux_dir=staging/"temporary_mux"
        v=build_demo_video(slide_dir,narration,audio_dir,mux_dir,
            declared_diagnostic_voice="en_US-ljspeech-medium LOCAL PORTABLE NONFORMAL",
            ffmpeg_bin=str(ffmpeg),ffprobe_bin="ffprobe")
        if (v.get("slide_count")!=academic["topic_count"]
            or v.get("status")!="DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION"
            or v.get("all_slide_midpoints_source_pixel_checked") is not True
            or len(v.get("video_slide_frame_alignment",[]))!=academic["topic_count"]
            or any(x["mean_absolute_rgb_fraction"]>.03 for x in v["video_slide_frame_alignment"])
            or v.get("publication_allowed") is not False):
            raise PortablePipelineError("Source-aligned full media output incomplete")
        video_dir=staging/"video"
        video_dir.mkdir()
        mp4_file=video_dir/"lecture_portable_neural_candidate.mp4"
        (mux_dir/"lecture_diagnostic_only.mp4").rename(mp4_file)
        mux_file=video_dir/"independent_mux_technical_report.json"
        (mux_dir/"diagnostic_av_receipt.json").rename(mux_file)
        shutil.rmtree(mux_dir)
        if sha_file(mp4_file)!=v["diagnostic_mp4_sha256"]:
            raise PortablePipelineError("Final video SHA changed during cleanup")
        if any(sha_file(Path(path))!=sha for path,sha in frozen.items()):
            raise PortablePipelineError("Original source/figure/model mutated during campaign")
        result={"schema_version":1,"status":"PORTABLE_REAL_LECTURE_VIDEO_CANDIDATE_NOT_PUBLISHED",
            "section_id":academic["section_id"],"slide_count":academic["topic_count"],
            "source_pdf_sha256":academic["source_pdf_sha256"],
            "original_contract_sha256":academic["manifest_sha256"],
            "academic_topic_audit_sha256":sha_file(academic_file),
            "slides_pdf_sha256":visual["rendered_pdf_sha256"],
            "source_pdf_figures_with_geometric_provenance":visual[
                "source_pdf_figures_with_geometric_provenance"],
            "all_figures_original_pdf_raster_and_nearby_caption_verified":visual[
                "all_figures_original_pdf_raster_and_nearby_caption_verified"],
            "independently_checked_typed_math_claims_count":visual[
                "independently_checked_typed_math_claims_count"],
            "audio_receipt_sha256":sha_file(audio_dir/"portable_audio_receipt.json"),
            "asr_advisory_sha256":sha_file(observed_path),
            "mp4_sha256":sha_file(mp4_file),
            "video_filename":"video/lecture_portable_neural_candidate.mp4",
            "technical_mux_report_sha256":sha_file(mux_file),
            "total_audio_seconds":audio["total_seconds"],
            "real_video_seconds":v["diagnostic_mp4_duration_seconds"],
            "video_frame_checks":v["video_slide_frame_alignment"],
            "academic_coverage_only_declared_topics":True,
            "fully_general_academic_synthesis_proven":False,
            "phonetic_accuracy_comprehensively_verified":False,
            "formal_voice_authorized":False,
            "copyright_distribution_authorized":False,
            "provider_calls":0,"publication_allowed":False}
        (staging/"portable_pipeline_receipt.json").write_text(json.dumps(result,indent=2))
        if new_output.exists():raise PortablePipelineError("Output destination race")
        os.rename(staging,new_output)
        return result
    finally:
        if staging.exists():shutil.rmtree(staging)

def main(argv=None):
    p=argparse.ArgumentParser()
    for name in ("stage","narration","plan","contract","model-dir","piper-python",
                 "vosk-dir","ffmpeg","new-output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args(argv)
    result=run_portable_pipeline(a.stage,a.narration,a.plan,a.contract,
        a.model_dir,a.piper_python,a.vosk_dir,a.ffmpeg,a.new_output)
    print(json.dumps({"section":result["section_id"],
        "slides":result["slide_count"],"seconds":result["real_video_seconds"],
        "publication_allowed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
