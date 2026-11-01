"""Section-agnostic, explicit-source-anchor academic coverage contract.

This validates enumerated topic coverage only. A manifest is a user/agent
assertion, not independent scientific proof that all curriculum is included.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file

class PortableSectionError(ValueError):pass

def clean(s:str)->str:
    return re.sub(r"\s+"," ",str(s).casefold()).strip()

def audit_portable_contract(source:Path,narration:Path,visual_plan:Path,manifest_file:Path)->dict:
    source,narration,visual_plan,manifest_file=map(Path,
        (source,narration,visual_plan,manifest_file))
    originals=(source,narration,visual_plan,manifest_file)
    if any(not f.is_file() or f.is_symlink() for f in originals):
        raise PortableSectionError("Four immutable section and contract files required")
    shas={str(p):sha_file(p) for p in originals}
    m=json.loads(manifest_file.read_text(encoding="utf8"))
    n=json.loads(narration.read_text(encoding="utf8"))
    v=json.loads(visual_plan.read_text(encoding="utf8"))
    topics=m.get("topics")
    if (m.get("schema_version")!=1
        or not isinstance(m.get("section_id"),str) or not m["section_id"].strip()
        or m.get("source_pdf_sha256")!=shas[str(source)]
        or m.get("narration_sha256")!=shas[str(narration)]
        or m.get("visual_plan_sha256")!=shas[str(visual_plan)]
        or not isinstance(m.get("start_marker"),str)
        or not m.get("start_marker")
        or m.get("publication_allowed") is not False
        or not isinstance(topics,list) or not 2<=len(topics)<=60
        or n.get("publication_allowed") is not False
        or v.get("publication_allowed") is not False
        or not isinstance(n.get("slides"),list)
        or not isinstance(v.get("slides"),list)
        or len(n["slides"])!=len(topics)
        or len(v["slides"])!=len(topics)
        or not isinstance(m.get("min_narration_words"),int)
        or not isinstance(m.get("max_narration_words"),int)
        or not 60<=m["min_narration_words"]<=m["max_narration_words"]<=250):
        raise PortableSectionError("Incomplete source-bound section contract or forged approval")
    with fitz.open(source) as pdf:
        raw=[clean(page.get_text("text")) for page in pdf]
    start=clean(m["start_marker"])
    if not 1<=len(raw)<=100 or not start or start not in raw[0]:
        raise PortableSectionError("Original section start marker not present on first page")
    # Printed running headers may repeat the section name before the actual
    # section heading. Last occurrence conservatively excludes that prefix.
    # This can reject legitimate early content, but cannot borrow earlier text.
    original_first=raw[0]
    raw[0]=start+" "+original_first.rsplit(start,1)[1]
    removed_prefix_chars=len(original_first)-len(raw[0])
    end=m.get("next_section_marker")
    if end is not None:
        if not isinstance(end,str) or not end.strip():
            raise PortableSectionError("Malformed adjacent-section boundary")
        marker=clean(end)
        if marker not in raw[-1]:
            raise PortableSectionError("Adjacent section boundary absent; fail closed")
        raw[-1]=raw[-1].split(marker,1)[0]
    elif m.get("end_of_pdf") is not True:
        raise PortableSectionError("End of target section must be independently bounded")
    seen=set();rows=[]
    for i,(topic,spoken,visible) in enumerate(zip(topics,n["slides"],v["slides"]),1):
        page=topic.get("source_page")
        tid=topic.get("topic_id")
        anchors=topic.get("source_anchors")
        terms=topic.get("required_terms")
        speech=spoken.get("narration")
        bullets=visible.get("bullets")
        if (not isinstance(tid,str) or not 2<=len(tid)<=90 or tid in seen
            or type(page) is not int or not 1<=page<=len(raw)
            or not isinstance(anchors,list) or not 1<=len(anchors)<=6
            or not isinstance(terms,list) or not 1<=len(terms)<=8
            or any(not isinstance(a,str) or not 3<=len(a)<=160 for a in anchors+terms)
            or spoken.get("slide")!=i or visible.get("slide")!=i
            or spoken.get("topic_id")!=tid or visible.get("topic_id")!=tid
            or spoken.get("source_page")!=page or visible.get("source_page")!=page
            or not isinstance(speech,str) or not speech.isascii()
            or not m["min_narration_words"]<=len(speech.split())<=m["max_narration_words"]
            or hashlib.sha256(speech.encode("utf8")).hexdigest()!=spoken.get("spoken_text_sha256")
            or not isinstance(bullets,list) or not 2<=len(bullets)<=5
            or any(not isinstance(b,str) or not 4<=len(b)<=150 for b in bullets)):
            raise PortableSectionError("Slide/topic/audio/visual alignment wrong")
        seen.add(tid)
        source_text=raw[page-1]
        visible_text=clean(visible.get("title","")+" "+" ".join(bullets))
        spoken_text=clean(speech)
        if (not all(clean(anchor) in source_text for anchor in anchors)
            or not all(clean(term) in spoken_text and clean(term) in visible_text
                       for term in terms)):
            raise PortableSectionError(f"Source or two-media topic anchor missing on slide {i}")
        rows.append({"slide":i,"topic_id":tid,"source_page":page,
             "source_anchors_verified":True,"spoken_visible_terms_verified":True,
             "narration_sha256":spoken["spoken_text_sha256"]})
    if any(sha_file(p)!=shas[str(p)] for p in originals):
        raise PortableSectionError("Source or manifest changed during source audit")
    return {"schema_version":1,
      "status":"PORTABLE_DECLARED_TOPIC_COVERAGE_VERIFIED_NOT_FULL_ACADEMIC",
      "section_id":m["section_id"],
      "source_pdf_sha256":shas[str(source)],
      "narration_sha256":shas[str(narration)],
      "visual_plan_sha256":shas[str(visual_plan)],
      "manifest_sha256":shas[str(manifest_file)],
      "topic_count":len(rows),"topics":rows,
      "preceding_first_page_characters_excluded":removed_prefix_chars,
      "next_section_excluded":end is not None,
      "self_declared_manifest_does_not_prove_all_source_topics_included":True,
      "independent_full_academic_certification":False,
      "formal_voice_authorized":False,"publication_allowed":False}

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("source","narration","visual-plan","manifest","new-report"):
        p.add_argument("--"+x,required=True,type=Path)
    a=p.parse_args(argv)
    report=audit_portable_contract(a.source,a.narration,a.visual_plan,a.manifest)
    out=a.new_report.resolve(strict=False)
    if (out.exists() or a.new_report.is_symlink() or not out.parent.is_dir()
        or any(x.casefold()=="my drive" for x in out.parts)):
        raise PortableSectionError("A fresh external coverage report required")
    with out.open("x",encoding="utf8") as f:json.dump(report,f,indent=2)
    print(json.dumps({"section_id":report["section_id"],
        "topic_count":report["topic_count"],"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
