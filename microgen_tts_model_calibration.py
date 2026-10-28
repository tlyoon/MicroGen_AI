"""Machine-checked model calibration using lecturer-labeled *real* WAV references.

ASR text can normalize away a phoneme error. A pair that labels a known
bad pronunciation as clean (or returns UNKNOWN) is NOT calibrated for that
pronunciation family. This is a narrowly scoped test, not population proof.
"""
from __future__ import annotations
from pathlib import Path
from microgen_tts_benchmark import validate_reference,sha256_file,score_recognition
from microgen_tts_acoustic_benchmark import detect_yay_case

class ModelCalibrationError(ValueError):
    pass

def check_model_calibration(manifest:dict,report:dict,wav_dir:Path,
                            *,expected_models:tuple[str,str])->dict:
    try:validate_reference(manifest,Path(wav_dir))
    except Exception as exc:raise ModelCalibrationError("Calibration reference WAVs not verified") from exc
    if (not isinstance(report,dict) or report.get("schema_version")!=1 or
        list(expected_models)!=report.get("model_names") or len(expected_models)!=2 or
        expected_models[0]==expected_models[1]):
        raise ModelCalibrationError("Calibration report has wrong model identities or schema")
    raw_rows=report.get("actual_audio_evidence")
    if not isinstance(raw_rows,list) or len(raw_rows)!=len(manifest["samples"]):
        raise ModelCalibrationError("Calibration report is incomplete")
    predictions={}
    for sample,row in zip(manifest["samples"],raw_rows):
        source=Path(wav_dir)/sample["filename"]
        if (not isinstance(row,dict) or row.get("id")!=sample["id"] or
            row.get("wav_sha256")!=sha256_file(source) or
            row.get("model_names")!=list(expected_models)):
            raise ModelCalibrationError("Calibration source hashes or case IDs differ")
        transcripts=row.get("transcripts")
        if not isinstance(transcripts,list) or len(transcripts)!=2:
            raise ModelCalibrationError("Calibration transcripts missing")
        generated=[]
        for t in transcripts:
            prediction=(detect_yay_case(t,int(sample.get("expected_occurrences",2)))
                        if isinstance(t,str) else "unknown")
            generated.append(prediction)
        if row.get("individual_predictions")!=generated:
            raise ModelCalibrationError("Declared acoustic predictions differ from transcripts")
        consensus=(generated[0] if generated[0]==generated[1] else "unknown")
        if row.get("prediction")!=consensus:
            raise ModelCalibrationError("Declared calibration consensus is inaccurate")
        predictions[sample["id"]]=consensus
    derived=score_recognition(manifest,predictions)
    claimed=report.get("metrics")
    if (not isinstance(claimed,dict) or
        any(claimed.get(key)!=derived[key]
            for key in ("sample_count","evaluated","coverage","confusion",
                        "recall","false_alarm_rate","precision","acceptance_pass"))):
        raise ModelCalibrationError("Calibration reported metrics differ from recomputation")
    unavailable=report.get("unavailable_models")
    if not isinstance(unavailable,list):
        raise ModelCalibrationError("Missing model-availability evidence")
    qualified=derived["acceptance_pass"] and not unavailable
    return {
        "schema_version":1,
        "tested_model_names":list(expected_models),
        "risk_family":"math_y_value_two_occurrences",
        "case_count":len(manifest["samples"]),
        "evaluated":derived["evaluated"],
        "coverage":derived["coverage"],
        "true_positive":derived["confusion"]["TP"],
        "false_negative":derived["confusion"]["FN"],
        "false_positive":derived["confusion"]["FP"],
        "true_negative":derived["confusion"]["TN"],
        "unavailable_models":list(unavailable),
        "qualified_for_tested_risk_family":bool(qualified),
        "manual_gate":False,
        "scope":"Only tested Y/yay vs why utterances; no general phonetic certification",
    }
