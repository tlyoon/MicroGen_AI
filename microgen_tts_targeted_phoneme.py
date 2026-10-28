"""Calibrated risk-scoped phonetic checks; never a global ASR replacement."""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Callable
from microgen_tts_blind_phoneme import probe_wav,digest
from microgen_tts_contrastive_calibration import calibrate
from microgen_tts_risk_register import find_pronunciation_risks
from text_to_speech_v25 import normalize_scientific_speech

class TargetedProbeError(ValueError):pass

def eligible_y_risks(text:str)->list[dict]:
    from dataclasses import asdict
    return [asdict(x) for x in find_pronunciation_risks(
        text,normalize_scientific_speech(text))
        if x.code=="math_letter_compound" and
        re.match(r"^[Yy]\s*[-\u2010-\u2015]\s*values?\b",x.source)]

def scan_stage(stage:Path,reference:dict,reference_folder:Path,
               model1:Callable,model2:Callable,*,models:tuple[str,str],
               max_probe_slides:int=12)->dict:
    stage=Path(stage)
    script=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    slides=script.get("slides",[])
    if not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise TargetedProbeError("Unordered source slide mapping")
    planned=[]
    for i,item in enumerate(slides,1):
        raw=str(item.get("tts_text") or item.get("narration") or "")
        risks=eligible_y_risks(raw)
        if risks:planned.append((i,risks))
    if not isinstance(max_probe_slides,int) or max_probe_slides<1 or len(planned)>max_probe_slides:
        raise TargetedProbeError("Risk-scoped audio probe exceeds allowed slide count")
    # Calibration calls are mandatory; no stale or unverified report shortcut.
    qualification=calibrate(reference,reference_folder,model1,model2,models=models)
    if not qualification["calibrated_for_tested_y_value_family"]:
        return {"schema_version":1,"calibration":qualification,
                "risk_slide_count":len(planned),"probe_rows":[],
                "blocked":True,"reason":"UNQUALIFIED_PHONETIC_JUDGES",
                "verified_error_free":False,"human_gate":False,"published":False}
    rows=[]
    for number,risks in planned:
        wav=stage/f"slide{number}.wav"
        first=probe_wav(wav,model1,model_identity=models[0])
        second=probe_wav(wav,model2,model_identity=models[1])
        labels=[first["label"],second["label"]]
        status=("Y_SOUND_AS_EXPECTED_ON_TESTED_CLASS" if labels==["WHY","WHY"]
                else "DETECTED_YAY_RISK" if "YAY" in labels
                else "UNRESOLVED_PHONETIC_RISK")
        rows.append({"slide":number,"source_risks":risks,
                     "wav_sha256":digest(wav),"models":list(models),
                     "judgments":[first,second],"status":status})
    return {"schema_version":1,"calibration":qualification,
            "risk_slide_count":len(planned),"probe_rows":rows,
            "blocked":any(x["status"]!="Y_SOUND_AS_EXPECTED_ON_TESTED_CLASS" for x in rows),
            "verified_error_free":False,"human_gate":False,"published":False,
            "scope":"One tested Y-value phoneme family only; other pronunciation/academic risks unresolved"}
