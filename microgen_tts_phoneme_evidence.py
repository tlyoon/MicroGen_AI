"""Verify risk-scoped WAV phoneme evidence against current source and baseline.

Content checks are not signatures. This prevents accidental stale/forged
self-inconsistent reports; a trusted execution boundary is still necessary.
"""
from __future__ import annotations
import json
from pathlib import Path
from microgen_tts_benchmark import validate_reference,sha256_file
from microgen_tts_targeted_phoneme import eligible_y_risks

class TargetedEvidenceError(ValueError):pass

def verify_scan(stage:Path,manifest:dict,reference_audio:Path,report:dict)->dict:
    if not isinstance(report,dict) or report.get("schema_version")!=1:
        raise TargetedEvidenceError("Unsupported targeted evidence")
    validate_reference(manifest,Path(reference_audio))
    calibration=report.get("calibration")
    if not isinstance(calibration,dict) or calibration.get("schema_version")!=1:
        raise TargetedEvidenceError("No calibration evidence")
    models=calibration.get("models")
    if (not isinstance(models,list) or len(models)!=2 or
        not all(isinstance(x,str) and x for x in models) or models[0]==models[1]):
        raise TargetedEvidenceError("Model identity invalid")
    cases=calibration.get("cases")
    if not isinstance(cases,list) or len(cases)!=len(manifest["samples"]):
        raise TargetedEvidenceError("Calibration cases incomplete")
    judgments_ok=True
    for item,row in zip(manifest["samples"],cases):
        if (row.get("id")!=item["id"] or row.get("reference_label")!=item["label"] or
            row.get("reference_sha256")!=sha256_file(Path(reference_audio)/item["filename"])):
            raise TargetedEvidenceError("Calibration source mismatch")
        expected="YAY" if item["label"]=="defect" else "WHY"
        answers=row.get("model_answers")
        if not isinstance(answers,list) or len(answers)!=2:
            raise TargetedEvidenceError("Incomplete calibration judge answers")
        expected_ok=all(a.get("label")==expected and a.get("model")==model and
                        a.get("wav_sha256")==row["reference_sha256"]
                        for a,model in zip(answers,models))
        if row.get("expected_phoneme")!=expected or row.get("both_detected_expected")!=expected_ok:
            raise TargetedEvidenceError("Calibration classification drift")
        judgments_ok &= expected_ok
    if (calibration.get("calibrated_for_tested_y_value_family")!=judgments_ok or
        calibration.get("observed_coverage")!=sum(bool(x["both_detected_expected"]) for x in cases)/len(cases)):
        raise TargetedEvidenceError("Calibration summary inconsistent")
    script=json.loads((Path(stage)/"script_tts.json").read_text(encoding="utf8"))
    slides=script.get("slides",[])
    expected=[]
    for number,item in enumerate(slides,1):
        risks=eligible_y_risks(str(item.get("tts_text") or item.get("narration") or ""))
        if risks:expected.append((number,risks))
    if report.get("risk_slide_count")!=len(expected):
        raise TargetedEvidenceError("Targeted slide coverage drift")
    rows=report.get("probe_rows")
    if not isinstance(rows,list):
        raise TargetedEvidenceError("Missing targeted probe rows")
    if not judgments_ok:
        if rows or not report.get("blocked"):
            raise TargetedEvidenceError("Unqualified models claimed results")
        return {"verified":True,"technically_cleared":False,
                "blockers":["unqualified_phonetic_models"],"models":models}
    if len(rows)!=len(expected):
        raise TargetedEvidenceError("Incomplete targeted slide evidence")
    blockers=[]
    for row,(slide,risks) in zip(rows,expected):
        digest=sha256_file(Path(stage)/f"slide{slide}.wav")
        if row.get("slide")!=slide or row.get("source_risks")!=risks or row.get("wav_sha256")!=digest:
            raise TargetedEvidenceError("Targeted slide or source drift")
        answers=row.get("judgments")
        if not isinstance(answers,list) or len(answers)!=2:
            raise TargetedEvidenceError("Missing judgment evidence")
        labels=[]
        for answer,model in zip(answers,models):
            if answer.get("model")!=model or answer.get("wav_sha256")!=digest:
                raise TargetedEvidenceError("Judgment/source SHA mismatch")
            labels.append(answer.get("label"))
        derived=("Y_SOUND_AS_EXPECTED_ON_TESTED_CLASS" if labels==["WHY","WHY"]
                 else "DETECTED_YAY_RISK" if "YAY" in labels
                 else "UNRESOLVED_PHONETIC_RISK")
        if row.get("status")!=derived:
            raise TargetedEvidenceError("Phoneme status falsified")
        if derived!="Y_SOUND_AS_EXPECTED_ON_TESTED_CLASS":
            blockers.append(f"slide_{slide}_{derived}")
    if report.get("blocked")!=bool(blockers):
        raise TargetedEvidenceError("Overall blocker summary is inconsistent")
    return {"verified":True,"technically_cleared":not blockers,
            "blockers":blockers,"models":models,
            "narrow_scope":"tested Y-value family only; no global pronunciation approval"}
