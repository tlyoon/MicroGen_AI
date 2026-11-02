"""Advisory source coverage and semantic-risk triage — synthetic only."""
import copy
import tempfile
from pathlib import Path
import pytest

from microgen_portable_semantic_coverage_triage import (
    SourceCoverageRiskError,profile_source_coverage)
from microgen_portable_private_authoring_gate import write_validated_stage
from test_microgen_portable_private_authoring_gate import construct


def test_synthetic_two_source_topics_have_traced_context_and_new_word_advisory():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source,packet,draft=construct(root)
        qa=profile_source_coverage(packet,draft)
        assert qa["source_passages_cited"]==2
        assert qa["source_passage_citation_fraction"]==1
        assert qa["source_passages_discovered"]==2
        assert len(qa["topic_context_audits"])==2
        assert not qa["semantic_entailment_independently_proven"]
        assert not qa["academic_completeness_proven"]
        assert qa["publication_allowed"] is False
        assert all(q["source_anchor_already_checked_by_pr247"]
                   for q in qa["topic_context_audits"])
        stage=root/"accepted"
        result=write_validated_stage(source,packet,draft,stage)
        triage=result["source_coverage_semantic_risk_triage"]
        assert triage["topic_count"]==2
        assert "source_coverage_semantic_risk_triage" in (
            stage/"authoring_private_qa.json").read_text()


def test_advisory_flags_important_unreferenced_source_without_blocking_draft():
    packet={"section_id":"B.2","source_pdf_sha256":"a"*64,"publication_allowed":False,
            "source_evidence":[
              {"passage_id":"s1","source_page":1,"text":"A model describes a measurement.",
               "figure_mentions":[]},
              {"passage_id":"s2","source_page":1,
               "text":"Example 7.2 Demonstrate how a speedometer uses miles and kilometers.",
               "figure_mentions":[]},
              {"passage_id":"s3","source_page":1,
               "text":"Figure 7.2 The measurement shows multiple speed scales.",
               "figure_mentions":["Figure 7.2"]},
              {"passage_id":"s4","source_page":2,
               "text":"Quick Quiz 7.2 Compare conversion factors.",
               "figure_mentions":[]}]}
    draft={"publication_allowed":False,"topics":[
       {"topic_id":"a","source_page":1,"source_passage_ids":["s1"],
        "title":"Physical models","bullets":["Models help reason"],
        "narration":"A model can organize measured information without changing the source."},
       {"topic_id":"b","source_page":1,"source_passage_ids":["s1"],
        "title":"Measurements","bullets":["Find representation"],
        "narration":"A physical model may be used to interpret observations."}
    ]}
    triage=profile_source_coverage(packet,draft)
    assert triage["source_passages_cited"]==1
    assert triage["unreferenced_passage_ids"]==["s2","s3","s4"]
    assert triage["important_context_candidates_count"]==3
    assert len(triage["unreferenced_important_context_candidates"])==3
    assert any("figure_reference_or_caption" in x["category_tags"]
               for x in triage["unreferenced_important_context_candidates"])
    assert all(x["unreferenced_advisory"] for x in
               triage["unreferenced_important_context_candidates"])
    assert not triage["uncited_passage_means_omitted_learning_objective"]
    assert triage["triage_is_advisory"]


@pytest.mark.parametrize("fault",[
    "duplicate_passage","unknown_passage","repeated_citation","bad_status",
    "missing_text","bad_topic_inventory","no_source","duplicate_order"
])
def test_unsafe_reference_data_not_accepted_as_coverage(fault):
    packet={"section_id":"1.1","source_pdf_sha256":"f"*64,
        "publication_allowed":False,"source_evidence":[
           {"passage_id":"x1","source_page":1,"text":"Energy is conserved.",
            "figure_mentions":[]}]}
    draft={"publication_allowed":False,"topics":[
         {"topic_id":"first","source_passage_ids":["x1"],
          "title":"Energy","bullets":["Physics works"],"narration":"A physical system."},
         {"topic_id":"second","source_passage_ids":["x1"],
          "title":"Physics","bullets":["Energy system"],"narration":"More physical detail."}]}
    if fault=="duplicate_passage":packet["source_evidence"].append(
       copy.deepcopy(packet["source_evidence"][0]))
    elif fault=="unknown_passage":draft["topics"][0]["source_passage_ids"]=["wrong"]
    elif fault=="repeated_citation":draft["topics"][1]["source_passage_ids"]=["x1","x1"]
    elif fault=="bad_status":draft["publication_allowed"]=True
    elif fault=="missing_text":packet["source_evidence"][0]["text"]=""
    elif fault=="bad_topic_inventory":draft["topics"]=[{}]
    elif fault=="no_source":packet["source_evidence"]=[]
    elif fault=="duplicate_order":packet["source_evidence"][0]["passage_id"]=None
    with pytest.raises(SourceCoverageRiskError):
        profile_source_coverage(packet,draft)
