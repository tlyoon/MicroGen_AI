"""Select only genuinely recorded, source-bound two-model phoneme calibrations.

This does NOT run models or prove their biological/acoustic validity. It
rejects every report that cannot demonstrate the two known outcomes and
never substitutes an unqualified model for a required machine QA gate.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_tts_benchmark import validate_reference,sha256_file
from microgen_tts_acoustic_qa import require_external_new_receipt

class SelectionError(ValueError):pass

def inspect_report(reference:dict,folder:Path,report:dict)->dict:
    valid={"qualified":False,"models":None,"reason":"INVALID_OR_UNQUALIFIED_EVIDENCE"}
    if not isinstance(report,dict) or report.get("schema_version")!=1:
        return valid
    if report.get("live_audio_requests_requested") is not True:
        return {**valid,"reason":"NOT_OBSERVED_LIVE_CALLS"}
    models=report.get("models")
    if (not isinstance(models,list) or len(models)!=2 or
        not all(isinstance(m,str) and m.strip() for m in models) or
        models[0]==models[1]):
        return {**valid,"reason":"NOT_TWO_DISTINCT_MODELS"}
    cases=report.get("cases")
    if not isinstance(cases,list) or len(cases)!=len(reference["samples"]):
        return {**valid,"models":models,"reason":"INCOMPLETE_REFERENCE_CASES"}
    passes=0
    for sample,case in zip(reference["samples"],cases):
        expected="YAY" if sample["label"]=="defect" else "WHY"
        digest=sha256_file(Path(folder)/sample["filename"])
        judgments=case.get("model_answers")
        if (case.get("id")!=sample["id"] or
            case.get("reference_label")!=sample["label"] or
            case.get("reference_sha256")!=digest or
            case.get("expected_phoneme")!=expected or
            not isinstance(judgments,list) or len(judgments)!=2):
            return {**valid,"models":models,"reason":"REFERENCE_OR_RESPONSE_MISMATCH"}
        if any(not isinstance(x,dict) or x.get("wav_sha256")!=digest or
               x.get("model")!=model or x.get("label") not in ("WHY","YAY","UNKNOWN")
               or x.get("used_expected_narration") is not False
               for x,model in zip(judgments,models)):
            return {**valid,"models":models,"reason":"JUDGE_SOURCE_OR_BLINDING_MISMATCH"}
        success=all(x["label"]==expected for x in judgments)
        if success!=case.get("both_detected_expected"):
            return {**valid,"models":models,"reason":"CASE_CLASSIFICATION_DRIFT"}
        passes+=success
    qualified=passes==len(cases)
    if (report.get("calibrated_for_tested_y_value_family")!=qualified or
        report.get("observed_coverage")!=passes/len(cases)):
        return {**valid,"models":models,"reason":"SUMMARY_CLASSIFICATION_DRIFT"}
    return {"qualified":qualified,"models":models,
            "reason":"QUALIFIED_ON_TESTED_REFERENCE_ONLY" if qualified
                     else "FAILED_REAL_AUDIO_REFERENCE",
            "case_count":len(cases),"correctly_classified":passes}

def select_pair(reference:dict,folder:Path,reported:list[dict],
                *,max_reports:int=12)->dict:
    validate_reference(reference,Path(folder))
    if type(max_reports) is not int or not 1<=max_reports<=30 or len(reported)>max_reports:
        raise SelectionError("Unbounded candidate reports are not permitted")
    inspected=[]
    for index,report in enumerate(reported):
        item=inspect_report(reference,folder,report)
        inspected.append({"candidate_index":index,**item})
    qualified=[item for item in inspected if item["qualified"]]
    qualified.sort(key=lambda x:(x["models"][0],x["models"][1],x["candidate_index"]))
    winner=qualified[0] if qualified else None
    return {"schema_version":1,"reference_family":"known_thomas_2_5_y_value_yay_why",
            "observed_reports":len(reported),"candidate_results":inspected,
            "selected_models":winner["models"] if winner else None,
            "selection_status":"TESTED_PAIR_FOUND" if winner else "NO_QUALIFIED_AUDIO_PAIR",
            "populational_phonetic_accuracy_proven":False,
            "manual_approval_required":False,"published":False}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("reference_manifest",type=Path)
    p.add_argument("reference_wav_folder",type=Path)
    p.add_argument("new_external_report",type=Path)
    p.add_argument("candidate_reports",type=Path,nargs="+")
    args=p.parse_args(argv)
    output=require_external_new_receipt(args.reference_wav_folder,args.new_external_report)
    reference=json.loads(args.reference_manifest.read_text(encoding="utf8"))
    candidates=[json.loads(path.read_text(encoding="utf8")) for path in args.candidate_reports]
    verdict=select_pair(reference,args.reference_wav_folder,candidates)
    with output.open("x",encoding="utf8") as f:
        f.write(json.dumps(verdict,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":verdict["selection_status"],
                      "selected_models":verdict["selected_models"],
                      "candidate_count":verdict["observed_reports"]}))
    return 0 if verdict["selected_models"] else 2
if __name__=="__main__":raise SystemExit(main())
