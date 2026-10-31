"""Source-verified, voice-neutral Serway narration and media handoff.

A work order is not a generated lecture, audio file or publication approval.
"""
import argparse
import json
from pathlib import Path
from microgen_serway_draft_audit import audit_serway_draft
from microgen_pronunciation_closed_loop import sha_file

class SerwayHandoffError(ValueError):
    pass

def plan_serway_handoff(stage: Path, draft: Path, evidence: Path) -> dict:
    evidence=Path(evidence)
    if not evidence.is_file() or evidence.is_symlink():
        raise SerwayHandoffError("Independent draft receipt required")
    source=audit_serway_draft(stage,draft)
    verified=json.loads(evidence.read_text(encoding="utf8"))
    if verified!=source or source["publication_allowed"] is not False:
        raise SerwayHandoffError("Source-draft evidence is stale or forged")
    manifest=json.loads((Path(draft)/"slide_draft_receipt.json").read_text(encoding="utf8"))
    rows=[]
    for i,item in enumerate(manifest["slides"],1):
        rows.append({
            "slide":i,"title":item["title"],"source_page":item["source_page"],
            "source_excerpt":item["source_excerpt"],
            "source_pdf_sha256":source["source_pdf_sha256"],
            "draft_pdf_sha256":source["draft_pdf_sha256"],
            "narration_text":None,
            "source_grounded_expansion_required":True,
            "historical_SI_context_required":i==4,
            "figure_academic_pixel_QA_required":i==5,
            "formal_voice":None,"production_wav":None,"production_mp4":None,
            "publication_allowed":False
        })
    gates=[
        ("full_source_scope","PENDING","Verbatim excerpts are not a complete lecture"),
        ("automated_figure_academic_QA","PENDING","Figure panel correctness must be verified"),
        ("complete_source_grounded_narration","PENDING","Full spoken script not generated"),
        ("formal_TTS_voice_authorization","UNCONFIGURED","Diagnostic Cloud TTS is not formal default"),
        ("source_bound_production_WAVs","PENDING","No eligible generated formal WAVs"),
        ("synchronized_lecture_MP4","PENDING","No complete synchronized video"),
        ("autonomous_academic_audio_video_acceptance","PENDING","No final full-media QA")
    ]
    return {
        "schema_version":1,"status":"HANDOFF_CREATED_MEDIA_NOT_READY",
        "audit_sha256":sha_file(evidence),
        "source_pdf_sha256":source["source_pdf_sha256"],
        "draft_pdf_sha256":source["draft_pdf_sha256"],
        "slide_count":len(rows),"narration_work_order":rows,
        "dependency_gates":[{"task":k,"state":s,"reason":v} for k,s,v in gates],
        "formal_voice_name":None,"formal_voice_authorized":False,
        "diagnostic_google_cloud_is_not_formal_voice":True,
        "provider_calls":0,"generated_wavs":False,"generated_mp4s":False,
        "autonomous_full_academic_QA_passed":False,
        "publication_allowed":False
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--draft",type=Path,required=True)
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--new-output",type=Path,required=True)
    a=p.parse_args(argv)
    output=a.new_output.resolve(strict=False)
    if (a.new_output.exists() or a.new_output.is_symlink()
        or not output.parent.is_dir()
        or a.stage.resolve(strict=True) in output.parents
        or a.draft.resolve(strict=True) in output.parents
        or any(k.casefold()=="my drive" for k in output.parts)):
        raise SerwayHandoffError("External, new, non-source output required")
    plan=plan_serway_handoff(a.stage,a.draft,a.audit)
    with output.open("x",encoding="utf8") as f: json.dump(plan,f,indent=2)
    print(json.dumps({"output":str(output),"slide_count":plan["slide_count"],
                      "formal_voice_authorized":False,"publication_allowed":False}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
