"""Private model-agnostic source-grounded lecture authoring gate.

An authorized writer must supply independently written teaching material.
This module does not use a cloud provider or pretend extractive PDF source text
is original lecture narration; it validates and packages a writer's output.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import pymupdf as fitz

from microgen_portable_source_equations import crop_sha
from microgen_source_passage_discovery import _heading_bound, _find_section_end_page
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import audit_portable_contract, clean
from microgen_source_passage_discovery import discover_passages
from microgen_portable_semantic_coverage_triage import profile_source_coverage

class AuthoringGateError(ValueError):
    pass

def canonical_hash(value:dict)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,
             separators=(",",":")).encode("utf8")).hexdigest()

def tokens(s):
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?",s.casefold())

def ngrams(s,n=12):
    ts=tokens(s)
    return {tuple(ts[i:i+n]) for i in range(len(ts)-n+1)}

def _source_numbers(text):
    return set(re.findall(r"(?<![a-zA-Z])\d+(?:\.\d+)?",text))

def _safe_output(output:Path,source:Path):
    dest=output.resolve(strict=False)
    if (output.exists() or output.is_symlink() or not dest.parent.is_dir()
        or source.resolve(strict=True) in (dest,*dest.parents)
        or any(x.casefold()=="my drive" for x in dest.parts)):
        raise AuthoringGateError("Fresh private output, separate from source and My Drive, required")
    return dest

def build_authoring_packet(source:Path,start_marker:str,next_marker:str|None=None,
                           *,end_of_pdf=False,section_id:str=""):
    discovery=discover_passages(source,start_marker,next_marker,end_of_pdf=end_of_pdf)
    if (not isinstance(section_id,str) or not 1<=len(section_id)<=30
        or not re.fullmatch(r"[\w.-]+",section_id)):
        raise AuthoringGateError("Explicit section ID required")
    return {
        "schema_version":1,
        "status":"PRIVATE_SOURCE_AUTHORING_PACKET_REQUIRES_INDEPENDENT_WRITER",
        "section_id":section_id,
        "source_pdf_sha256":discovery["source_pdf_sha256"],
        "source_page_count":discovery["source_page_count"],
        "start_marker":start_marker,
        "next_section_marker":next_marker,
        "end_of_pdf":bool(end_of_pdf),
        "source_evidence":[{"passage_id":p["passage_id"],
             "source_page":p["source_page"],"source_bbox":p["source_bbox"],
             "source_sha256":p["source_sha256"],"text":p["text"],
             "figure_mentions":p["figure_mentions"]} for p in discovery["passages"]],
        "source_passage_count":discovery["passage_count"],
        "generation_policy":{
            "draft_format":"model_response_json",
            "instruction":"Write NEW educational narration and slide titles/bullets in your own words; do not copy long source passages. Keep technical claims faithful and independently supported. Each topic must cite bounded source passage IDs and a short original source anchor; do not include previous/next sections. Avoid invented numeric values and unrelated concepts.",
            "topic_count_range":[2,60],
            "narration_words":[60,250],
            "bullets_per_slide":[2,5],
            "no_provider_invoked":True,
            "source_must_remain_private":True
        },
        "formal_voice_authorized":False,
        "publication_allowed":False,
        "independent_scientific_certification":False
    }

def _validate_draft(packet:dict,draft:dict,source_pdf:Path)->tuple[list,dict]:
    if (draft.get("schema_version")!=1
        or draft.get("source_pdf_sha256")!=packet["source_pdf_sha256"]
        or draft.get("section_id")!=packet["section_id"]
        or draft.get("packet_sha256")!=canonical_hash(packet)
        or draft.get("publication_allowed") is not False
        or not isinstance(draft.get("topics"),list)
        or not 2<=len(draft["topics"])<=60):
        raise AuthoringGateError("Draft schema, source identity or nonpublication marker invalid")
    by_id={p["passage_id"]:p for p in packet["source_evidence"]}
    assert len(by_id)==len(packet["source_evidence"])
    known_texts=[p["text"] for p in packet["source_evidence"]]
    orig_ngrams=set().union(*(ngrams(t) for t in known_texts))
    seen=set(); used=set(); lessons=[]; pages=[]; verified_numeric=[]
    original_pdf=fitz.open(source_pdf)
    try:
        first_heading_end=_heading_bound(original_pdf[0],packet["start_marker"],True)[1]
        if packet["next_section_marker"]:
            next_heading_page,next_heading_start,_=_find_section_end_page(
                original_pdf,packet["next_section_marker"],first_heading_end)
        else:
            next_heading_page=len(original_pdf)-1
            next_heading_start=None
    finally:
        original_pdf.close()
    narration_ngrams=Counter()
    for idx,item in enumerate(draft["topics"],1):
        if not isinstance(item,dict):
            raise AuthoringGateError("Malformed model-authored topic")
        tid=item.get("topic_id")
        page=item.get("source_page")
        ids=item.get("source_passage_ids")
        anchor=item.get("source_anchor")
        terms=item.get("required_terms")
        title=item.get("title")
        bullets=item.get("bullets")
        speech=item.get("narration")
        if (not isinstance(tid,str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,79}",tid)
            or tid in seen or type(page) is not int
            or not isinstance(ids,list) or not 1<=len(ids)<=5
            or len(ids)!=len(set(ids)) or any(i not in by_id for i in ids)
            or any(by_id[i]["source_page"]!=page for i in ids)
            or not isinstance(anchor,str) or not 8<=len(anchor)<=160
            or not isinstance(terms,list) or not 1<=len(terms)<=4
            or any(not isinstance(t,str) or not 3<=len(t)<=45 or not t.isascii()
                   for t in terms)
            or not isinstance(title,str) or not 5<=len(title)<=90
            or not isinstance(bullets,list) or not 2<=len(bullets)<=5
            or any(not isinstance(b,str) or not 5<=len(b)<=88 for b in bullets)
            or not isinstance(speech,str) or not 60<=len(speech.split())<=250
            or any(not x.isascii() for x in (title,speech,*bullets))
            or any("\\" in x or "$" in x for x in (title,*bullets))):
            raise AuthoringGateError(f"Topic {idx}: invalid structure or unsafe text")
        source=" ".join(by_id[i]["text"] for i in ids)
        visible=clean(title+" "+" ".join(bullets))
        if (clean(anchor) not in clean(source)
            or any(clean(term) not in clean(source)
                   or clean(term) not in clean(speech)
                   or clean(term) not in visible for term in terms)):
            raise AuthoringGateError(f"Topic {idx}: uncited source fact or missing media term")
        # Dense exact source quotations and fabricated displayed numbers fail.
        combined=title+" "+" ".join(bullets)+" "+speech
        if orig_ngrams.intersection(ngrams(combined)):
            raise AuthoringGateError(f"Topic {idx}: 12-word near-verbatim copied source passage")
        permitted_numbers=_source_numbers(source)
        sidecars=item.get("source_numeric_evidence",[])
        if not isinstance(sidecars,list) or len(sidecars)>3:
            raise AuthoringGateError("Invalid extra source numeric evidence")
        for extra in sidecars:
            if not isinstance(extra,dict) or set(extra)!={
                "source_page","source_bbox","source_crop_sha256","numeric_tokens"}:
                raise AuthoringGateError("Incomplete source diagram numeric evidence")
            region=extra["source_bbox"]
            if (type(extra["source_page"]) is not int
                or extra["source_page"]!=page or not isinstance(region,list)
                or len(region)!=4 or any(type(v) not in (int,float) for v in region)
                or not isinstance(extra["numeric_tokens"],list)
                or not 1<=len(extra["numeric_tokens"])<=8):
                raise AuthoringGateError("Unsafe source numeric region")
            with fitz.open(source_pdf) as pdf:
                box=fitz.Rect(region)
                pg=pdf[page-1]
                if (not box.is_valid or box.is_empty or box.width<15 or box.height<10
                    or not pg.rect.contains(box)
                    or (page==1 and box.y0<first_heading_end)
                    or (next_heading_start is not None
                        and (page-1>next_heading_page or
                             (page-1==next_heading_page and
                              box.y1>next_heading_start)))
                    or crop_sha(pg,box)!=extra["source_crop_sha256"]):
                    raise AuthoringGateError("Numeric source not bounded and hash verified")
                observed=_source_numbers(" ".join(pg.get_text(clip=box).split()))
                if any(type(v) is not str or v not in observed
                       for v in extra["numeric_tokens"]):
                    raise AuthoringGateError("Declared numeric value absent from original source crop")
                permitted_numbers.update(extra["numeric_tokens"])
                verified_numeric.append({"slide":idx,"source_page":page,
                    "source_crop_sha256":extra["source_crop_sha256"],
                    "numeric_tokens":extra["numeric_tokens"]})
        added_numbers=_source_numbers(combined)-permitted_numbers
        if added_numbers:
            raise AuthoringGateError(f"Topic {idx}: numerical data absent from selected source evidence")
        shingles=ngrams(speech,10)
        if sum(narration_ngrams[x]>0 for x in shingles)>max(1,len(shingles)//3):
            raise AuthoringGateError(f"Topic {idx}: excessive reused narration across slides")
        narration_ngrams.update(shingles)
        seen.add(tid);used.update(ids);pages.append(page)
        lessons.append(item)
    if pages!=sorted(pages):
        raise AuthoringGateError("Topic order contradicts physical source page progression")
    report={
        "schema_version":1,
        "status":"PRIVATE_AUTHORING_FORMAT_SOURCE_COPY_AND_ALIGNMENT_PASSED_NOT_SCIENCE",
        "source_pdf_sha256":packet["source_pdf_sha256"],
        "source_packet_sha256":canonical_hash(packet),
        "topic_count":len(lessons),
        "passage_count":len(by_id),
        "passages_used_count":len(used),
        "verified_source_numeric_regions":verified_numeric,
        "unmapped_passage_ids":[i for i in by_id if i not in used],
        "all_topics_original_source_anchor_and_both_media_checked":True,
        "copying_12_gram_and_unknown_numbers_guard_passed":True,
        "semantic_entailment_independently_proven":False,
        "complete_academic_coverage_proven":False,
        "publication_allowed":False,
        "formal_voice_authorized":False
    }
    return lessons,report



def _line_safe_source_anchor(original_anchor:str,passage_text:str,
                             source_page_lines:str)->tuple[str,bool]:
    """Preserve original citation despite PDF superscript reflow differences.

    Superscript text may read "109" as a block, but "10 9" as separate glyph
    spans.  Retain the longest ORIGINAL prefix also present unambiguously in
    the physical PDF line representation; never invent words or edit source.
    """
    if (not isinstance(original_anchor,str)
        or not isinstance(passage_text,str) or not isinstance(source_page_lines,str)
        or clean(original_anchor) not in clean(passage_text)):
        raise AuthoringGateError("Source anchor is not in its cited passage")
    text=clean(source_page_lines)
    if clean(original_anchor) in text:
        return original_anchor,False
    words=original_anchor.split()
    for count in range(len(words)-1,4,-1):
        candidate=" ".join(words[:count]).strip()
        simple=clean(candidate)
        if (24<=len(candidate)<=160 and len(simple)>=20
            and simple in clean(passage_text)
            and text.count(simple)==1):
            return candidate,True
    raise AuthoringGateError("No unambiguous original source-line-compatible citation prefix")


def _ensure_source_line_compatible_anchors(source:Path,packet:dict,
                                            lessons:list)->tuple[list,list]:
    """Repair only anchor strings, not narration, source PDF or model draft."""
    by_id={x["passage_id"]:x for x in packet["source_evidence"]}
    replacements=[]
    adjusted=[]
    with fitz.open(source) as original:
        page_cache={}
        for index,item in enumerate(lessons,1):
            page=item["source_page"]
            if page not in page_cache:
                p=original[page-1]
                lines=[line for block in p.get_text("dict")["blocks"]
                       if block.get("type")==0
                       for line in block.get("lines",[])]
                page_cache[page]=" ".join(" ".join(
                    span.get("text","") for span in line["spans"]) for line in lines)
            passage=" ".join(by_id[i]["text"] for i in item["source_passage_ids"])
            candidate,changed=_line_safe_source_anchor(
                item["source_anchor"],passage,page_cache[page])
            updated=dict(item)
            updated["source_anchor"]=candidate
            adjusted.append(updated)
            if changed:
                replacements.append({
                    "slide":index,"source_page":page,
                    "source_passage_ids":item["source_passage_ids"],
                    "original_source_anchor_sha256":hashlib.sha256(
                        item["source_anchor"].encode("utf8")).hexdigest(),
                    "adopted_source_anchor_sha256":hashlib.sha256(
                        candidate.encode("utf8")).hexdigest(),
                    "only_trailing_unstable_glyphs_trimmed":True,
                    "source_content_changed":False
                })
    return adjusted,replacements

def write_validated_stage(source:Path,packet:dict,draft:dict,new_stage:Path):
    source,new_stage=Path(source),Path(new_stage)
    if source.is_symlink() or not source.is_file():
        raise AuthoringGateError("Immutable source PDF required")
    dest=_safe_output(new_stage,source)
    original_sha=sha_file(source)
    if (packet.get("source_pdf_sha256")!=original_sha
        or packet.get("publication_allowed") is not False
        or packet.get("formal_voice_authorized") is not False):
        raise AuthoringGateError("Source/packet drift or forbidden approval")
    # A draft with a matching forged packet hash cannot redefine source text.
    # Independently regenerate the source-bounded passage evidence on each call.
    fresh=build_authoring_packet(source,packet.get("start_marker"),
        packet.get("next_section_marker"),
        end_of_pdf=packet.get("end_of_pdf") is True,
        section_id=packet.get("section_id"))
    if canonical_hash(fresh)!=canonical_hash(packet):
        raise AuthoringGateError("Authoring packet differs from original PDF source")
    lessons,qa=_validate_draft(packet,draft,source)
    lessons,repairs=_ensure_source_line_compatible_anchors(source,packet,lessons)
    qa["source_anchor_line_reflow_repairs"]=repairs
    qa["source_anchor_line_reflow_repair_count"]=len(repairs)
    qa["source_coverage_semantic_risk_triage"]=profile_source_coverage(packet,draft)
    n={"publication_allowed":False,"formal_voice_authorized":False,"slides":[]}
    v={"publication_allowed":False,"slides":[]}
    topics=[]
    for idx,item in enumerate(lessons,1):
        speech=item["narration"].strip()
        common={"slide":idx,"topic_id":item["topic_id"],
                "source_page":item["source_page"]}
        n["slides"].append({**common,"narration":speech,
            "spoken_text_sha256":hashlib.sha256(speech.encode("utf8")).hexdigest()})
        v["slides"].append({**common,"title":item["title"],
                           "bullets":item["bullets"]})
        topics.append({"topic_id":item["topic_id"],
                       "source_page":item["source_page"],
                       "source_anchors":[item["source_anchor"]],
                       "required_terms":item["required_terms"]})
    base=dest.parent
    temporary=Path(tempfile.mkdtemp(prefix=".microgen-authoring-",dir=base))
    try:
        shutil.copyfile(source,temporary/"source.pdf")
        nar=temporary/"narration.json";plan=temporary/"plan.json"
        nar.write_text(json.dumps(n,indent=2),encoding="utf8")
        plan.write_text(json.dumps(v,indent=2),encoding="utf8")
        manifest={
            "schema_version":1,"section_id":packet["section_id"],
            "source_pdf_sha256":original_sha,
            "narration_sha256":sha_file(nar),
            "visual_plan_sha256":sha_file(plan),
            "start_marker":packet["start_marker"],
            "next_section_marker":packet["next_section_marker"],
            "min_narration_words":60,"max_narration_words":250,
            "topics":topics,"publication_allowed":False,
            "authoring_source_packet_sha256":canonical_hash(packet),
            "authoring_draft_sha256":canonical_hash(draft),
            "authoring_verified_numeric_source_regions":qa["verified_source_numeric_regions"]
        }
        if packet["end_of_pdf"]:manifest["end_of_pdf"]=True
        con=temporary/"contract.json"
        con.write_text(json.dumps(manifest,indent=2),encoding="utf8")
        academic=audit_portable_contract(temporary/"source.pdf",nar,plan,con)
        if academic["topic_count"]!=len(lessons):
            raise AuthoringGateError("Source media contract disagrees with authoring output")
        qa["existing_portable_section_contract_passed"]=True
        qa["contract_sha256"]=sha_file(con)
        (temporary/"authoring_private_qa.json").write_text(
            json.dumps(qa,indent=2),encoding="utf8")
        if sha_file(source)!=original_sha or dest.exists():
            raise AuthoringGateError("Input changed or destination created during authoring")
        os.rename(temporary,dest)
        return qa
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--start-marker",required=True)
    parser.add_argument("--next-marker")
    parser.add_argument("--end-of-pdf",action="store_true")
    parser.add_argument("--section-id",required=True)
    parser.add_argument("--new-private-packet",type=Path)
    parser.add_argument("--draft-response",type=Path)
    parser.add_argument("--new-private-stage",type=Path)
    a=parser.parse_args(argv)
    packet=build_authoring_packet(a.source,a.start_marker,a.next_marker,
                                  end_of_pdf=a.end_of_pdf,section_id=a.section_id)
    if a.new_private_packet is not None:
        dest=_safe_output(a.new_private_packet,a.source)
        with dest.open("x",encoding="utf8") as f:
            json.dump(packet,f,indent=2,ensure_ascii=True)
    if a.draft_response:
        if not a.new_private_stage:
            raise AuthoringGateError("Fresh stage required when validating an authored draft")
        result=write_validated_stage(a.source,packet,
          json.loads(a.draft_response.read_text(encoding="utf8")),
          a.new_private_stage)
        print(json.dumps({"topics":result["topic_count"],
                          "unmapped_source_passages":len(result["unmapped_passage_ids"]),
                          "publication_allowed":False}))
    elif not a.new_private_packet:
        raise AuthoringGateError("Request either a private packet or a validated authored stage")
    return 0

if __name__=="__main__":raise SystemExit(main())
