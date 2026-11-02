"""Wholly synthetic authoring/contract/copyright tests; no protected course data."""
import copy
import json
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_portable_private_authoring_gate import (
    AuthoringGateError,build_authoring_packet,write_validated_stage,
    canonical_hash)
from microgen_portable_slide_render import render_portable_slides
from microgen_portable_source_equations import crop_sha
from microgen_portable_section_contract import audit_portable_contract
from microgen_pronunciation_closed_loop import sha_file

START="B.2 Evidence and Models"
NEXT="B.3 Other Topic"

def create_source(root):
    p=root/"input.pdf";pdf=fitz.open()
    page=pdf.new_page()
    page.insert_text((45,85),"Earlier unrelated section about meteorites.")
    page.insert_text((45,201),START,fontsize=13)
    page.insert_textbox(fitz.Rect(45,240,520,360),
       "A model can simplify a physical system by selecting a useful representation. "
       "The model is constructed around a question and tested against an observation. "*2,
       fontsize=12)
    page.insert_text((45,470),"25.0 degrees and 50.0 m")
    page=pdf.new_page()
    page.insert_textbox(fitz.Rect(45,100,520,260),
       "A graph shows how a measured quantity changes with time. "
       "An experiment may use a graph to compare repeated observations. "*3,fontsize=12)
    page.insert_text((45,326),NEXT)
    page.insert_textbox(fitz.Rect(45,350,510,470),
       "Unrelated novel principle should not be included in the previous section. "*3,fontsize=12)
    pdf.save(p);pdf.close();return p

def spoken(term,first=True):
    if first:
        return ("This learning segment examines the model as a way to reason about a physical system. "
          "We start by stating what the simplified picture is supposed to explain. "
          "Next we ask which physical information is essential for the chosen question. "
          "An observation can then be compared with the prediction of the proposed model. "
          "That comparison is useful because it tells us whether the simplified account "
          "helps us understand the situation, or whether more details should be included. "
          "This is an exercise in setting up a physical explanation with clear assumptions.")
    return ("This segment introduces a graph as a way to organize measurements. "
       "Start by reading what quantity is measured and which other quantity it depends on. "
       "Consider how several observations might be compared on the same set of axes. "
       "The shape of a graph can be informative only after its labels are understood. "
       "When the recorded points change, ask which interpretation is supported by the observations. "
       "This method helps us communicate patterns without requiring a drawing of the entire apparatus. "
       "It also gives a clear starting point for a later quantitative analysis.")

def construct(root):
    src=create_source(root)
    packet=build_authoring_packet(src,START,NEXT,section_id="B.2")
    assert packet["source_passage_count"]>=2
    p1=next(p for p in packet["source_evidence"] if p["source_page"]==1)
    p2=next(p for p in packet["source_evidence"] if p["source_page"]==2)
    response={
      "schema_version":1,"source_pdf_sha256":sha_file(src),
      "packet_sha256":canonical_hash(packet),"section_id":"B.2",
      "publication_allowed":False,
      "topics":[{
        "topic_id":"physical_model","source_page":1,
        "source_passage_ids":[p1["passage_id"]],
        "source_anchor":"A model can simplify a physical system",
        "required_terms":["model"],
        "title":"A Practical Model for Physical Questions",
        "bullets":["Specify the question before simplifying",
                   "Use a model to test a proposed explanation"],
        "narration":spoken("model")
      },{
        "topic_id":"graph_representation","source_page":2,
        "source_passage_ids":[p2["passage_id"]],
        "source_anchor":"A graph shows how a measured quantity",
        "required_terms":["graph"],
        "title":"Interpreting a Graph of Measurements",
        "bullets":["A graph organizes measured information",
                   "Compare an observation across experiments"],
        "narration":spoken("graph",False)
      }]
    }
    return src,packet,response

def test_source_to_authoring_to_original_portable_renderer():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        sha=sha_file(src)
        stage=root/"private-stage"
        evidence=write_validated_stage(src,packet,draft,stage)
        assert evidence["topic_count"]==2
        assert evidence["existing_portable_section_contract_passed"]
        assert not evidence["semantic_entailment_independently_proven"]
        files=(stage/"source.pdf",stage/"narration.json",
               stage/"plan.json",stage/"contract.json")
        audit=audit_portable_contract(*files)
        assert audit["topic_count"]==2
        rendered=render_portable_slides(stage,*files[1:],root/"slides")
        assert rendered["slide_count"]==2
        assert not rendered["publication_allowed"]
        assert sha_file(src)==sha
        assert not (stage/"original_textbook_figure.png").exists()
        assert all("Unrelated novel" not in t["narration"]
                   for t in json.loads(files[1].read_text())["slides"])

@pytest.mark.parametrize("edit",[
  "forged_packet","wrong_source","copied_source","fake_number","missing_term",
  "unlinked_passage","borrow_next","same_narration","wrong_page",
  "duplicate_topic","malformed_title","approval"
])
def test_untrusted_authored_drafts_rejected_without_creating_stage(edit):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        if edit=="forged_packet":draft["packet_sha256"]="0"*64
        elif edit=="wrong_source":draft["source_pdf_sha256"]="f"*64
        elif edit=="copied_source":
            p=packet["source_evidence"][0]["text"]
            draft["topics"][0]["narration"]+=" "+p*3
        elif edit=="fake_number":draft["topics"][0]["narration"]+=" 12345."
        elif edit=="missing_term":draft["topics"][1]["required_terms"]=["theory"]
        elif edit=="unlinked_passage":draft["topics"][0]["source_passage_ids"]=["wrong"]
        elif edit=="borrow_next":draft["topics"][1]["source_anchor"]="Unrelated novel principle"
        elif edit=="same_narration":draft["topics"][1]["narration"]=spoken("model")
        elif edit=="wrong_page":draft["topics"][1]["source_page"]=1
        elif edit=="duplicate_topic":draft["topics"][1]["topic_id"]="physical_model"
        elif edit=="malformed_title":draft["topics"][0]["title"]="Unprintable math $"
        elif edit=="approval":draft["publication_allowed"]=True
        with pytest.raises(AuthoringGateError):
            write_validated_stage(src,packet,draft,root/"private-stage")
        assert not (root/"private-stage").exists()

def test_mutated_source_and_existing_output_rejected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        out=root/"stage"
        write_validated_stage(src,packet,draft,out)
        previous=sha_file(out/"contract.json")
        with pytest.raises(AuthoringGateError):
            write_validated_stage(src,packet,draft,out)
        assert sha_file(out/"contract.json")==previous
        src.write_bytes(src.read_bytes()+b"\n")
        with pytest.raises(AuthoringGateError):
            write_validated_stage(src,packet,draft,root/"new")
        assert not (root/"new").exists()


@pytest.mark.parametrize("fault",["valid","wrong_value","changed_hash","wrong_page",
                                  "prior_section_region","next_section_region",
                                  "no_region"])
def test_optional_source_figure_numeric_labels_are_proven_from_pdf(fault):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src,packet,draft=construct(root)
        with fitz.open(src) as pdf:
            box=fitz.Rect(35,450,350,493)
            original_sha=crop_sha(pdf[0],box)
        sidecar={
            "source_page":1,"source_bbox":list(box),
            "source_crop_sha256":original_sha,
            "numeric_tokens":["25.0","50.0"]
        }
        draft["topics"][0]["narration"]+=(
            " The measured angle is 25.0 degrees, and the distance is 50.0 m.")
        if fault=="wrong_value":sidecar["numeric_tokens"]=["26.0"]
        elif fault=="changed_hash":sidecar["source_crop_sha256"]="f"*64
        elif fault=="wrong_page":sidecar["source_page"]=2
        elif fault=="prior_section_region":sidecar["source_bbox"]=[35,60,350,110]
        elif fault=="next_section_region":
            sidecar["source_page"]=2
            sidecar["source_bbox"]=[35,350,350,445]
        elif fault=="no_region":sidecar=None
        if sidecar: draft["topics"][0]["source_numeric_evidence"]=[sidecar]
        out=root/"private"
        if fault=="valid":
            qa=write_validated_stage(src,packet,draft,out)
            assert len(qa["verified_source_numeric_regions"])==1
            assert qa["verified_source_numeric_regions"][0]["numeric_tokens"]==[
                "25.0","50.0"]
            assert not qa["publication_allowed"]
        else:
            with pytest.raises(AuthoringGateError):
                write_validated_stage(src,packet,draft,out)
            assert not out.exists()


def test_forged_packet_and_matching_forged_draft_hash_still_rejected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src,packet,draft=construct(root)
        packet["source_evidence"][0]["text"]="A model can simplify a physical system. Fake text."
        draft["packet_sha256"]=canonical_hash(packet)
        with pytest.raises(AuthoringGateError):
            write_validated_stage(src,packet,draft,root/"never")
        assert not (root/"never").exists()
