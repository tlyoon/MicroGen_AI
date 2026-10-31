"""Verifiable formal-TTS *input* bundle after source/figure/diagnostic QA.

No synthesis and no default production narrator. Diagnostics cannot be promoted
by copying or renaming their receipt, even when the A/V checks pass.
"""
from __future__ import annotations
import argparse,json,os,shutil,tempfile
from pathlib import Path
from microgen_pronunciation_closed_loop import sha_file
from microgen_provider_voice_feasibility import ORIGINAL_VOICE

class FormalVoiceHandoffError(ValueError):pass

def prepare_formal_voice_handoff(narration:Path,critical_claims:Path,
                                 figure_panels:Path,diagnostic_dir:Path)->dict:
    narration,critical_claims,figure_panels,diagnostic_dir=map(
        Path,(narration,critical_claims,figure_panels,diagnostic_dir))
    video=diagnostic_dir/"lecture_diagnostic_only.mp4"
    av_receipt=diagnostic_dir/"diagnostic_av_receipt.json"
    sources={"narration":narration,"academic":critical_claims,"figure":figure_panels,
             "video":video,"av_receipt":av_receipt}
    if any(p.is_symlink() or not p.is_file() for p in sources.values()):
        raise FormalVoiceHandoffError("Immutable source-bound input and real diagnostic video required")
    hashes={key:sha_file(path) for key,path in sources.items()}
    n=json.loads(narration.read_text(encoding="utf8"))
    a=json.loads(critical_claims.read_text(encoding="utf8"))
    f=json.loads(figure_panels.read_text(encoding="utf8"))
    av=json.loads(av_receipt.read_text(encoding="utf8"))
    if (n.get("status")!="EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED"
        or n.get("publication_allowed") is not False
        or n.get("formal_voice_authorized") is not False
        or a.get("status")!="EIGHT_CRITICAL_SOURCE_CLAIM_GROUPS_SPOT_CHECKED"
        or a.get("narration_qa_sha256")!=hashes["narration"]
        or a.get("publication_allowed") is not False
        or f.get("status")!="ORIGINAL_TWO_PANEL_FIGURE_PIXEL_IDENTITY_VERIFIED"
        or f.get("narration_sha256")!=hashes["narration"]
        or f.get("critical_claim_report_sha256")!=hashes["academic"]
        or f.get("source_pdf_sha256")!=a.get("source_pdf_sha256")
        or f.get("teaching_pdf_sha256")!=a.get("teaching_slides_sha256")
        or f.get("publication_allowed") is not False
        or av.get("status")!="DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION"
        or av.get("diagnostic_mp4_sha256")!=hashes["video"]
        or av.get("narration_qa_sha256")!=hashes["narration"]
        or av.get("rendered_pdf_sha256")!=a.get("teaching_slides_sha256")
        or av.get("publication_allowed") is not False
        or av.get("voice_is_formal") is not False
        or av.get("formal_voice_authorized") is not False
        or av.get("all_slide_midpoints_source_pixel_checked") is not True
        or av.get("slide_count")!=8 or n.get("slide_count")!=8):
        raise FormalVoiceHandoffError("Source/figure/A-V chain incomplete or falsely promoted")
    if (not isinstance(a.get("critical_claim_groups"),list)
        or len(a["critical_claim_groups"])!=8
        or any(row.get("slide")!=i or row.get("critical_fact_spot_checks_passed") is not True
               for i,row in enumerate(a["critical_claim_groups"],1))
        or not isinstance(f.get("panels"),list)
        or len(f["panels"])!=2
        or [x.get("panel") for x in f["panels"]]!=["a_left","b_right"]
        or any(x.get("source_pixel_identity_verified") is not True
               or not isinstance(x.get("normalised_rgb_difference"),(float,int))
               or x["normalised_rgb_difference"]>1/255 for x in f["panels"])
        or not isinstance(av.get("video_slide_frame_alignment"),list)
        or len(av["video_slide_frame_alignment"])!=8
        or any(v.get("slide")!=i
               or v.get("matches_original_slide_under_8pct_threshold") is not True
               or not isinstance(v.get("mean_absolute_rgb_fraction"),(int,float))
               or v["mean_absolute_rgb_fraction"]>.08
               for i,v in enumerate(av["video_slide_frame_alignment"],1))):
        raise FormalVoiceHandoffError("Full diagnostic slide alignment is mandatory")
    if abs(av["diagnostic_mp4_duration_seconds"]-av["total_input_audio_seconds"])>max(
        2.,av["total_input_audio_seconds"]*.02):
        raise FormalVoiceHandoffError("Diagnostic video timing drift outside contract")
    if not (0<n["slide_count"]<=20 and len(n.get("slides",[]))==n["slide_count"]):
        raise FormalVoiceHandoffError("Full source-bound narration inventory required")
    rows=[]
    seen=set()
    for i,row in enumerate(n["slides"],1):
        speech=row.get("narration")
        if (row.get("slide")!=i or not isinstance(speech,str)
            or not speech.isascii() or not speech.strip()
            or row.get("review_state")!="DRAFT_NEEDS_INDEPENDENT_ACADEMIC_QA"
            or row.get("source_pdf_sha256")!=a["source_pdf_sha256"]
            or row.get("spoken_text_sha256")!=__import__("hashlib").sha256(
                speech.encode("utf8")).hexdigest()
            or row["spoken_text_sha256"] in seen):
            raise FormalVoiceHandoffError("Proposed formal TTS text is not exact verified draft")
        seen.add(row["spoken_text_sha256"])
        rows.append({"slide":i,"source_page":row["source_page"],
            "source_pdf_sha256":a["source_pdf_sha256"],
            "teaching_pdf_sha256":a["teaching_slides_sha256"],
            "input_text":speech,"text_sha256":row["spoken_text_sha256"],
            "formal_audio_path":None,"formal_audio_sha256":None,
            "pronunciation_verified":False,"production_tts_authorized":False})
    if any(sha_file(path)!=hashes[key] for key,path in sources.items()):
        raise FormalVoiceHandoffError("Source changed during formal voice handoff")
    blockers=[
        "FORMAL_TTS_PROVIDER_AND_VOICE_NOT_CONTRACT_AUTHORIZED",
        "FULL_SCIENTIFIC_ACCURACY_NOT_INDEPENDENTLY_CERTIFIED",
        "ACOUSTIC_TECHNICAL_TERMS_NOT_PHONETICALLY_VERIFIED",
        "PRODUCTION_WAVS_AND_SYNCHRONIZED_MP4_NOT_GENERATED",
        "PUBLICATION_LICENSE_AND_RELEASE_AUTHORIZATION_NOT_CONFIRMED",
    ]
    return {"schema_version":1,
        "status":"FORMAL_TTS_INPUT_BUNDLE_READY_PRODUCTION_BLOCKED",
        "source_ledger_sha256":hashes["academic"],
        "figure_panel_audit_sha256":hashes["figure"],
        "narration_qa_sha256":hashes["narration"],
        "diagnostic_video_sha256":hashes["video"],
        "diagnostic_receipt_sha256":hashes["av_receipt"],
        "diagnostic_voice_name":av["declared_diagnostic_voice"],
        "diagnostic_voice_cannot_be_default_formal":True,
        "formal_voice_provider":None,"formal_voice_name":None,
        "historical_configured_voice_name":ORIGINAL_VOICE,
        "historical_voice_is_not_formal_call_authorization":True,
        "language_code":"en-US","requested_audio_format":"mono-pcm16-wav",
        "voice_synthesis_calls":0,"slide_count":len(rows),
        "requests":rows,"blocking_conditions":blockers,
        "formal_production_ready":False,
        "full_lecture_academically_verified":False,
        "publication_allowed":False}

def save_formal_voice_handoff(narration,critical_claims,figure_panels,
                              diagnostic_dir,new_output):
    out=Path(new_output).resolve(strict=False)
    parents=[Path(p).resolve(strict=True) for p in (
        narration,critical_claims,figure_panels)]
    if (Path(new_output).exists() or Path(new_output).is_symlink()
        or not out.parent.is_dir()
        or out in parents or any(p.casefold()=="my drive" for p in out.parts)
        or Path(diagnostic_dir).resolve(strict=True) in out.parents):
        raise FormalVoiceHandoffError("Fresh external formal voice handoff required")
    report=prepare_formal_voice_handoff(narration,critical_claims,figure_panels,diagnostic_dir)
    with out.open("x",encoding="utf8") as f:json.dump(report,f,indent=2)
    return report

def main(argv=None):
    parser=argparse.ArgumentParser()
    for item in ("narration-qa","critical-claims","figure-panels","diagnostic-dir","new-output"):
        parser.add_argument("--"+item,type=Path,required=True)
    a=parser.parse_args(argv)
    o=save_formal_voice_handoff(a.narration_qa,a.critical_claims,a.figure_panels,
                                 a.diagnostic_dir,a.new_output)
    print(json.dumps({"output":str(a.new_output),"requests":o["slide_count"],
                      "production_blockers":len(o["blocking_conditions"]),
                      "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
