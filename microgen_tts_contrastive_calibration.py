"""Ground direct phonetic judgments in lecturer-labeled, SHA-pinned audio."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Callable
from microgen_tts_benchmark import validate_reference,sha256_file
from microgen_tts_blind_phoneme import probe_wav,gemini_phoneme_judge
from microgen_tts_acoustic_qa import require_external_new_receipt

class ContrastCalibrationError(ValueError): pass

def calibrate(manifest:dict,root:Path,first:Callable,second:Callable,
              *,models:tuple[str,str],max_requests:int=4)->dict:
    if len(models)!=2 or not all(isinstance(v,str) and v for v in models) or models[0]==models[1]:
        raise ContrastCalibrationError("Two distinct audio model identities required")
    validate_reference(manifest,Path(root))
    cases=manifest["samples"]
    if len(cases)!=2 or {x["label"] for x in cases}!={"defect","correct"}:
        raise ContrastCalibrationError("Requires one verified bad and one verified good WAV")
    if type(max_requests) is not int or max_requests<2*len(cases):
        raise ContrastCalibrationError("Unsafe request budget")
    attempts=[]
    for case in cases:
        wav=Path(root)/case["filename"]
        answers=[probe_wav(wav,callback,model_identity=name)
                 for callback,name in ((first,models[0]),(second,models[1]))]
        expected="YAY" if case["label"]=="defect" else "WHY"
        attempts.append({"id":case["id"],"reference_label":case["label"],
            "reference_sha256":sha256_file(wav),"expected_phoneme":expected,
            "model_answers":answers,
            "both_detected_expected":all(x["label"]==expected for x in answers)})
    valid=all(x["both_detected_expected"] for x in attempts)
    return {"schema_version":1,"method":"contrastive_audio_only_yay_why",
            "models":list(models),"cases":attempts,"count":len(attempts),
            "observed_coverage":sum(x["both_detected_expected"] for x in attempts)/len(attempts),
            "calibrated_for_tested_y_value_family":valid,"general_phonetic_validity":False,
            "human_approval":False,"publishable":False}

def main(argv=None):
    a=argparse.ArgumentParser()
    a.add_argument("manifest",type=Path);a.add_argument("wav_directory",type=Path)
    a.add_argument("new_external_report",type=Path)
    a.add_argument("--primary",default="gemini-3.5-flash")
    a.add_argument("--secondary",default="gemini-3.8-flash")
    a.add_argument("--live",action="store_true")
    args=a.parse_args(argv)
    if args.primary==args.secondary:a.error("Model identities must differ")
    out=require_external_new_receipt(args.wav_directory,args.new_external_report)
    dataset=json.loads(args.manifest.read_text(encoding="utf8"))
    validate_reference(dataset,args.wav_directory)
    if args.live:
        from dotenv import load_dotenv
        from gemini_keys import get_gemini_api_keys
        load_dotenv(Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Microvid"/".env")
        keys=get_gemini_api_keys()
        if not keys:raise ContrastCalibrationError("No configured audio credentials")
        judges=(gemini_phoneme_judge(keys[0],model=args.primary),
                gemini_phoneme_judge(keys[0],model=args.secondary))
    else:
        judges=(lambda *_:"UNKNOWN",lambda *_:"UNKNOWN")
    report=calibrate(dataset,args.wav_directory,*judges,
                     models=(args.primary,args.secondary))
    report["live_audio_requests_requested"]=bool(args.live)
    with out.open("x",encoding="utf8") as f:
        f.write(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"qualified":report["calibrated_for_tested_y_value_family"],
                      "coverage":report["observed_coverage"],"report":str(out)}))
    return 0 if report["calibrated_for_tested_y_value_family"] else 2
if __name__=="__main__":raise SystemExit(main())
