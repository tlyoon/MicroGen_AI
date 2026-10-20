"""Complete, hash-bound human listening queue for every TTS slide.

The queue is not a review receipt. It deliberately never sets approved=True.
A person, using a separate trusted signing system, must review exact WAV
hashes before any listening authorization is possible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from microgen_tts_risk_register import build_risk_register
from microgen_tts_provenance import digest_file
from text_to_speech_v25 import normalize_scientific_speech

class ListeningQueueError(ValueError):
    pass

def prepare_listening_queue(stage:Path, *,
                            clip_manifest:dict|None=None,
                            clip_folder:Path|None=None)->dict:
    stage=Path(stage)
    sidecar=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=sidecar.get("slides",[])
    if not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise ListeningQueueError("Narration slide order invalid")
    hashes=[digest_file(stage/f"slide{i}.wav") for i in range(1,len(slides)+1)]
    from microgen_tts_risk_register import durations_from_wavs
    durations=durations_from_wavs(stage,len(slides))
    risk=build_risk_register(slides,normalize_scientific_speech,durations,wav_sha256=hashes)
    clip_index={}
    if clip_manifest is not None:
        if not isinstance(clip_manifest.get("excerpts"),list) or clip_folder is None:
            raise ListeningQueueError("Clips require manifest and folder")
        for item in clip_manifest["excerpts"]:
            idx=item.get("slide")
            if not isinstance(idx,int) or not (1<=idx<=len(slides)):
                raise ListeningQueueError("Invalid clip slide index")
            if item.get("input_sha256")!=hashes[idx-1]:
                raise ListeningQueueError("Clip source audio hash drift")
            filename=item.get("clip_name")
            if (not isinstance(filename,str) or
                Path(filename).name!=filename or filename in (".","..")):
                raise ListeningQueueError("Unsafe clip name")
            clip=clip_folder/filename
            if not clip.is_file() or digest_file(clip)!=item.get("clip_sha256"):
                raise ListeningQueueError("Clip hash mismatch")
            clip_index.setdefault(idx,[]).append({
                "filename":filename,
                "sha256":item["clip_sha256"],
                "source_expression":item.get("source_excerpt"),
                "timing_is_only_approximate":True,
            })
    rows=[]
    for row in risk["slides"]:
        number=row["slide"]
        risks=row["risks"]
        priority=("HIGH_CONFIRMED_RISK_CLASS"
                  if any(x["code"] in ("math_letter_compound","math_c_sentence") for x in risks)
                  else "MATHEMATICAL_RISK" if risks else "WHOLE_SLIDE_SPOT_CHECK")
        rows.append({
            "slide":number,
            "wav_name":f"slide{number}.wav",
            "wav_sha256":row["audio_wav_sha256"],
            "tts_source_sha256":row["tts_source_sha256"],
            "spoken_input_sha256":row["spoken_input_sha256"],
            "start_seconds":row["slide_start_seconds"],
            "end_seconds":row["slide_end_seconds"],
            "priority":priority,
            "risk_expressions":[{
               "source":item["source"],"kind":item["code"],
               "expected_spoken":item["expected_spoken"],
            } for item in risks],
            "suggested_review_clips":clip_index.get(number,[]),
            "review_status":"NOT_REVIEWED",
            "listening_approved":False,
            "review_question":"Listen to whole slide. Do actual spoken words and mathematical letter names match the intended script?",
        })
    return {
        "schema_version":1,
        "source_script_sha256":digest_file(stage/"script_tts.json"),
        "slide_count":len(rows),
        "risk_flags":risk["risk_count"],
        "slides_requiring_listening":list(range(1,len(rows)+1)),
        "rows":rows,
        "listening_approved":False,
        "publishable":False,
        "signed_review_receipt_created":False,
        "note":"Reviewer decisions must come from an independent human and bind to these exact WAV hashes.",
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",type=Path)
    parser.add_argument("new_output",type=Path)
    parser.add_argument("--clip-manifest",type=Path)
    parser.add_argument("--clip-folder",type=Path)
    args=parser.parse_args(argv)
    if args.new_output.exists() or args.new_output.is_symlink():
        parser.error("Refusing to overwrite existing listening queue")
    manifest=(json.loads(args.clip_manifest.read_text(encoding="utf8"))
              if args.clip_manifest else None)
    result=prepare_listening_queue(args.stage,clip_manifest=manifest,
                                   clip_folder=args.clip_folder)
    with args.new_output.open("x",encoding="utf8") as f:
        f.write(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"slides":result["slide_count"],"risk_flags":result["risk_flags"],
                      "approved":False,"path":str(args.new_output)}))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
