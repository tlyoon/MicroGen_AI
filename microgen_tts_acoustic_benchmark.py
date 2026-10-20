"""Script-blind dual-model real audio benchmark; no score without observed ASR.

Text recognition can silently normalize an audible mistake. Detection results
are an ASR proxy only, NEVER proof of actual phoneme/letter pronunciation.
"""
from __future__ import annotations
import argparse
import json
import re
import wave
from pathlib import Path
from typing import Callable

from microgen_tts_benchmark import validate_reference,score_recognition,BenchmarkError,sha256_file

Y_VALUE = re.compile(r"\b(why|yay)\s+values?\b",re.I)


def preflight_benchmark(manifest:dict,audio_dir:Path,*,
                        max_audio_seconds:float=240.,
                        max_calls:int=10)->dict:
    """Budget real WAV input BEFORE invoking any audio provider."""
    validate_reference(manifest,Path(audio_dir))
    if (type(max_audio_seconds) not in (int,float) or max_audio_seconds<=0 or
        type(max_calls) is not int or max_calls<1):
        raise BenchmarkError("Invalid real-audio benchmark budget")
    requests=2*len(manifest["samples"])
    if requests>max_calls:
        raise BenchmarkError("Real-audio benchmark exceeds request limit")
    duration=0.
    for sample in manifest["samples"]:
        p=Path(audio_dir)/sample["filename"]
        if p.stat().st_size>18_000_000:
            raise BenchmarkError("Real-audio benchmark sample exceeds inline audio limit")
        with wave.open(str(p),"rb") as w:
            if w.getframerate()<=0 or w.getnframes()<=0:
                raise BenchmarkError("Invalid benchmark WAV")
            duration+=w.getnframes()/w.getframerate()
        if 2*duration>max_audio_seconds:
            raise BenchmarkError("Real-audio benchmark exceeds input duration limit")
    return {"planned_requests":requests,
            "planned_input_audio_seconds":round(2*duration,6),
            "monetary_cost_estimate":None}

def detect_yay_case(transcript:str, expected_occurrences:int=2)->str:
    """Only classify explicit transcribed word forms; math 'y' is ambiguous."""
    if not isinstance(transcript,str) or "[unclear]" in transcript.lower():
        return "unknown"
    matches=Y_VALUE.findall(transcript)
    if len(matches)!=expected_occurrences:
        return "unknown"
    return "flag" if any(x.lower()=="yay" for x in matches) else "clear"

def run_dual_model_benchmark(manifest:dict, audio_dir:Path,
                             first:Callable[[Path],str],
                             second:Callable[[Path],str],
                             *, model_names:tuple[str,str]) -> dict:
    if (len(model_names)!=2 or any(not x for x in model_names) or
        model_names[0]==model_names[1]):
        raise BenchmarkError("Two distinct model identities required")
    validate_reference(manifest,Path(audio_dir))
    original_hashes={item["id"]:sha256_file(Path(audio_dir)/item["filename"])
                     for item in manifest["samples"]}
    predictions={}
    evidence=[]
    unavailable=[False,False]
    for item in manifest["samples"]:
        f=Path(audio_dir)/item["filename"]
        guesses=[]
        transcripts=[]
        for index,model in enumerate((first,second)):
            if unavailable[index]:
                transcripts.append(None)
                guesses.append("unknown")
                continue
            try:
                spoken=str(model(f)).strip()
                transcripts.append(spoken)
                guesses.append(detect_yay_case(
                    spoken,int(item.get("expected_occurrences",2))))
            except Exception:
                unavailable[index]=True
                transcripts.append(None)
                guesses.append("unknown")
        if guesses==["flag","flag"]:
            prediction="flag"
        elif guesses==["clear","clear"]:
            prediction="clear"
        else:
            prediction="unknown"
        predictions[item["id"]]=prediction
        evidence.append({
            "id":item["id"],"wav_sha256":sha256_file(f),
            "model_names":list(model_names),"individual_predictions":guesses,
            "transcripts":transcripts,
            "prediction":prediction,
            "evaluation_method":"independent_script_blind_ASR_text_cues_not_phoneme_proof",
        })
    for item in manifest["samples"]:
        if sha256_file(Path(audio_dir)/item["filename"])!=original_hashes[item["id"]]:
            raise BenchmarkError("Benchmark WAV changed during recognition")
    score=score_recognition(manifest,predictions)
    return {
        "schema_version":1,
        "model_names":list(model_names),
        "actual_audio_evidence":evidence,
        "unavailable_models":[model_names[n] for n,missing in enumerate(unavailable) if missing],
        "metrics":score,
        "human_listening_approved":False,
        "population_error_rate_established":False,
        "publishable":False,
    }

def main(argv=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("manifest",type=Path)
    p.add_argument("audio_folder",type=Path)
    p.add_argument("new_report",type=Path)
    p.add_argument("--first-model",default="gemini-3.5-flash")
    p.add_argument("--second-model",default="gemini-3.8-flash")
    p.add_argument("--live",action="store_true",help="Opt in to real billed audio model calls")
    p.add_argument("--max-input-audio-seconds",type=float,default=240.)
    p.add_argument("--max-requests",type=int,default=10)
    args=p.parse_args(argv)
    from microgen_tts_acoustic_qa import require_external_new_receipt
    out=require_external_new_receipt(args.audio_folder,args.new_report)
    data=json.loads(args.manifest.read_text(encoding="utf-8"))
    budget=preflight_benchmark(data,args.audio_folder,
                               max_audio_seconds=args.max_input_audio_seconds,
                               max_calls=args.max_requests)
    if args.live:
        from dotenv import load_dotenv
        from gemini_keys import get_gemini_api_keys
        from microgen_tts_acoustic_qa import gemini_audio_recognizer
        import os
        load_dotenv(Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Microvid"/".env")
        keys=get_gemini_api_keys()
        if not keys:
            raise BenchmarkError("No configured acoustic analysis key")
        model1=gemini_audio_recognizer(keys[0],model=args.first_model)
        model2=gemini_audio_recognizer(keys[0],model=args.second_model)
    else:
        # Explicit no-cost mode; UNKNOWN rather than pretending to transcribe
        model1=lambda _: ""
        model2=lambda _: ""
    report=run_dual_model_benchmark(data,args.audio_folder,model1,model2,
            model_names=(args.first_model,args.second_model))
    report["preflight_budget"]=budget
    report["recognition_calls_executed"]=bool(args.live)
    report["inference_mode"]="live_audio_models" if args.live else "no_network_unknown_by_design"
    # NO overwrite, even if two concurrent jobs race.
    with out.open("x",encoding="utf-8") as handle:
        handle.write(json.dumps(report,indent=2,ensure_ascii=False))
    m=report["metrics"]
    print(json.dumps({"report":str(args.new_report),"coverage":m["coverage"],
                      "confusion":m["confusion"],"unavailable_models":report["unavailable_models"],
                      "acceptance_pass":m["acceptance_pass"]}))
    return 0 if m["acceptance_pass"] else 2
if __name__=="__main__":
    raise SystemExit(main())
