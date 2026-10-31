"""Fourteen source-grounded Serway neural TTS candidates; never a formal voice.

Source, narrated input, PDF, checked academic report and local ONNX model are
SHA-pinned. Generates only private off-line, original-preserving outputs. A
clean PCM/ASR report cannot certify pronunciation or copyrighted release.
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
from microgen_offline_neural_voice import MODEL_BASENAME, inspect_voice_probe
from microgen_pronunciation_closed_loop import sha_file

class ExpandedTtsError(ValueError): pass

# Unambiguous markup only. Never silently rewrite prose abbreviations "C."
# or isolated variables with no documented mathematical context.
MATH_SYMBOL_PATTERNS = (
    # Confirmed by local paired audio ASR diagnostic: "Planck constant"
    # was rendered "plane constant"; a separate "Plank constant" trial
    # was recognized as "plank constant". Visual/source name unchanged.
    (re.compile(r"\bPlanck(?=\s+constant\b)"), lambda m: "Plank"),
    (re.compile(r"\\dot\{([A-Za-z])\}"), lambda m: m.group(1)+" dot"),
    (re.compile(r"\b([A-Za-z])-dot\b"), lambda m: m.group(1)+" dot"),
    (re.compile(r"\\rho\b"), lambda m: "rho"),
    (re.compile(r"\\Delta\b"), lambda m: "delta"),
)

def prepare_spoken_text(text:str)->tuple[str,list[str]]:
    if not isinstance(text,str) or len(text)>2800:
        raise ExpandedTtsError("Malformed or unbounded speech input")
    modified=text
    corrections=[]
    for pattern,replace in MATH_SYMBOL_PATTERNS:
        updated,count=pattern.subn(replace,modified)
        if count:corrections.append(pattern.pattern)
        modified=updated
    if (not modified.isascii()
        or re.search(r"\\(?:dot|frac|begin|end|sqrt)\b|<[^>]*>",modified)
        or re.search(r"(?<!\w)[A-Za-z]\.(?!\w)",modified)):
        raise ExpandedTtsError("Ambiguous single-letter/LaTeX speech requires explicit math handling")
    return modified,corrections

def validate_model(model_dir:Path)->dict:
    folder=Path(model_dir)
    model=folder/MODEL_BASENAME
    config=folder/(MODEL_BASENAME+".json")
    card=folder/"MODEL_CARD"
    if folder.is_symlink() or not folder.is_dir() or any(
        not p.is_file() or p.is_symlink() for p in (model,config,card)):
        raise ExpandedTtsError("Local neural model and original license metadata are necessary")
    data=json.loads(config.read_text(encoding="utf8"))
    card_text=card.read_text(encoding="utf8").lower()
    if (data.get("audio",{}).get("sample_rate")!=22050
        or data.get("num_speakers")!=1
        or data.get("language",{}).get("code")!="en_US"
        or model.stat().st_size<10000
        or not all(s in card_text for s in
            ("license: public domain","trained from scratch","us english female voice"))):
        raise ExpandedTtsError("Audio model metadata or documented dataset license invalid")
    return {"model_sha256":sha_file(model),"model_card_sha256":sha_file(card),
        "model_config_sha256":sha_file(config),
        "model_name":MODEL_BASENAME.replace(".onnx",""),
        "training_dataset_declared_public_domain":True,
        "voice_weights_redistribution_independently_cleared":False}

def prepare_request(stage:Path,narration:Path,deck:Path,academic_report:Path,
                    model_dir:Path)->dict:
    stage,narration,deck,academic_report=map(Path,(stage,narration,deck,academic_report))
    source=stage/"source.pdf";figure=stage/"Figure 1.1.png"
    pdf=deck/"slides_teaching_candidate.pdf"
    receipt=deck/"teaching_slide_receipt.json"
    files=(source,figure,narration,pdf,receipt,academic_report)
    if any(not p.is_file() or p.is_symlink() for p in files):
        raise ExpandedTtsError("Source-locked academic and visual evidence missing")
    original={str(p):sha_file(p) for p in files}
    n=json.loads(narration.read_text(encoding="utf8"))
    audit=json.loads(academic_report.read_text(encoding="utf8"))
    deck_info=json.loads(receipt.read_text(encoding="utf8"))
    if (n.get("status")!="EXPANDED_SECTION_1_1_NARRATION_DRAFT_UNAPPROVED"
        or n.get("slide_count")!=14 or len(n.get("slides",[]))!=14
        or n.get("publication_allowed") is not False
        or n.get("formal_voice_authorized") is not False
        or n.get("source_pdf_sha256")!=original[str(source)]
        or audit.get("status")!="FOURTEEN_SECTION_1_1_CONCEPT_GROUPS_COVERED_SPOT_CHECKED"
        or audit.get("slide_count")!=14 or len(audit.get("topic_groups",[]))!=14
        or not audit.get("section_scope_end_before_next_section")
        or audit.get("source_pdf_sha256")!=original[str(source)]
        or audit.get("figure_sha256")!=original[str(figure)]
        or audit.get("narration_qa_sha256")!=original[str(narration)]
        or audit.get("rendered_teaching_pdf_sha256")!=original[str(pdf)]
        or audit.get("publication_allowed") is not False
        or deck_info.get("status")!="EXPANDED_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
        or deck_info.get("rendered_pdf_sha256")!=original[str(pdf)]
        or deck_info.get("narration_qa_sha256")!=original[str(narration)]
        or deck_info.get("figure_sha256")!=original[str(figure)]
        or deck_info.get("figure_slide")!=7
        or deck_info.get("historical_si_slide")!=6
        or deck_info.get("publication_allowed") is not False):
        raise ExpandedTtsError("Real source/academic/visual chain mismatched or falsely released")
    rows=[]
    seen=set()
    for i,(entry,topic,slide) in enumerate(
        zip(n["slides"],audit["topic_groups"],deck_info["slides"]),1):
        speech=entry.get("narration")
        if (type(entry.get("slide")) is not int or entry["slide"]!=i
            or topic.get("slide")!=i or slide.get("slide")!=i
            or topic.get("topic_id")!=entry.get("topic_id")
            or topic.get("source_page")!=entry.get("source_page")
            or slide.get("source_page")!=entry.get("source_page")
            or topic.get("original_page_anchors_verified") is not True
            or topic.get("spoken_and_visible_concept_terms_verified") is not True
            or topic.get("topic_id") in seen
            or not isinstance(speech,str) or not 140<=len(speech.split())<=180
            or entry.get("spoken_text_sha256")!=hashlib.sha256(speech.encode()).hexdigest()
            or slide.get("narration_sha256")!=entry.get("spoken_text_sha256")):
            raise ExpandedTtsError("One of fourteen original narrations lacks source evidence")
        seen.add(topic["topic_id"])
        spoken,changes=prepare_spoken_text(speech)
        rows.append({"slide":i,"topic_id":topic["topic_id"],
            "original_text_sha256":entry["spoken_text_sha256"],
            "synthesis_text":spoken,
            "synthesis_text_sha256":hashlib.sha256(spoken.encode()).hexdigest(),
            "unambiguous_math_pronunciation_expansions":changes})
    voice=validate_model(model_dir)
    if any(sha_file(p)!=original[str(p)] for p in files):
        raise ExpandedTtsError("Original academic evidence changed during qualification")
    return {"status":"FOURTEEN_SOURCE_BOUND_NEURAL_INPUTS_QUALIFIED_NOT_FORMAL",
        "slide_count":14,"requests":rows,**voice,
        "source_pdf_sha256":original[str(source)],
        "figure_sha256":original[str(figure)],
        "academic_report_sha256":original[str(academic_report)],
        "narration_qa_sha256":original[str(narration)],
        "deck_sha256":original[str(pdf)],
        "qualified_voice_for_formal_production":False,
        "dataset_license_claim_not_weights_reuse_grant":True,
        "no_paid_provider_calls":True,"publication_allowed":False}

def synthesize_expanded(stage:Path,narration:Path,deck:Path,academic_report:Path,
                        model_dir:Path,piper_python:Path,new_dir:Path)->dict:
    order=prepare_request(stage,narration,deck,academic_report,model_dir)
    output=Path(new_dir).resolve(strict=False)
    executable=Path(piper_python)
    if (output.exists() or Path(new_dir).is_symlink() or not output.parent.is_dir()
        or not executable.is_file() or executable.is_symlink()
        or Path(model_dir).resolve(strict=True) in output.parents
        or any(k.casefold()=="my drive" for k in output.parts)):
        raise ExpandedTtsError("New private output and explicit isolated interpreter required")
    temporary=Path(tempfile.mkdtemp(prefix=".microgen-serway14-tts-",dir=output.parent))
    try:
        payload=temporary/"private_speech_inputs.json"
        payload.write_text(json.dumps([{
            "slide":r["slide"],"text":r["synthesis_text"]} for r in order["requests"]]))
        code=("import json,sys,pathlib,wave;"
              "from piper import PiperVoice;"
              "v=PiperVoice.load(sys.argv[1]);"
              "rows=json.load(open(sys.argv[2],encoding='utf8'));"
              "folder=pathlib.Path(sys.argv[3]);"
              "assert len(rows)==14;"
              "\nfor r in rows:"
              "\n assert 1<=r['slide']<=14;"
              "\n path=folder/('slide%02d.wav'%r['slide']);"
              "\n with wave.open(str(path),'wb') as wav:v.synthesize_wav(r['text'],wav)")
        run=subprocess.run([str(executable),"-c",code,
            str(Path(model_dir)/MODEL_BASENAME),str(payload),str(temporary)],
            capture_output=True,text=True,timeout=1200)
        if run.returncode:
            raise ExpandedTtsError("Offline Piper failed: "+run.stderr[-550:])
        payload.unlink()
        report=verify_audio(temporary,order)
        report.update({"schema_version":1,"status":"FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL",
                       "technical_term_phonetics_fully_proven":False,
                       "formal_voice_authorized":False,
                       "formal_production_audio":False,
                       "provider_calls":0,"publication_allowed":False})
        (temporary/"expanded_neural_qa_receipt.json").write_text(
            json.dumps(report,indent=2),encoding="utf8")
        if validate_model(model_dir)["model_sha256"]!=order["model_sha256"]:
            raise ExpandedTtsError("Neural model changed during offline synthesis")
        if output.exists():raise ExpandedTtsError("Output destination race")
        os.rename(temporary,output)
        return report
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def verify_audio(folder:Path,order:dict)->dict:
    if order.get("slide_count")!=14 or len(order.get("requests",[]))!=14:
        raise ExpandedTtsError("Complete academic narration bundle required")
    items=[]
    for i,r in enumerate(order["requests"],1):
        path=Path(folder)/f"slide{i:02d}.wav"
        if (r.get("slide")!=i or not path.is_file() or path.is_symlink()
            or hashlib.sha256(r["synthesis_text"].encode()).hexdigest()
               !=r["synthesis_text_sha256"]):
            raise ExpandedTtsError(f"Unbound or missing PCM slide {i}")
        p=inspect_voice_probe(path,min_seconds=20,max_seconds=240)
        items.append({"slide":i,"topic_id":r["topic_id"],
            "synthesis_text_sha256":r["synthesis_text_sha256"],
            "original_text_sha256":r["original_text_sha256"],
            "source_pdf_sha256":order["source_pdf_sha256"],
            "academic_report_sha256":order["academic_report_sha256"],
            "deck_sha256":order["deck_sha256"],"file":path.name,**p,
            "formal_voice_authorized":False})
    if len(items)!=14:
        raise ExpandedTtsError("Partial neural lecture narration")
    return {"slide_count":14,"slides":items,
        "total_seconds":round(sum(x["seconds"] for x in items),3),
        "academic_source_sha256":order["source_pdf_sha256"],
        "academic_report_sha256":order["academic_report_sha256"],
        "deck_sha256":order["deck_sha256"],
        "narration_qa_sha256":order["narration_qa_sha256"],
        "voice_model_sha256":order["model_sha256"],
        "voice_model_card_sha256":order["model_card_sha256"],
        "dataset_declared_public_domain":True,
        "voice_weights_redistribution_independently_cleared":False}

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("stage","narration","deck","academic-report","model-dir","piper-python","new-dir"):
        p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args(argv)
    result=synthesize_expanded(a.stage,a.narration,a.deck,a.academic_report,
        a.model_dir,a.piper_python,a.new_dir)
    print(json.dumps({"slides":result["slide_count"],"seconds":result["total_seconds"],
        "status":result["status"],"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
