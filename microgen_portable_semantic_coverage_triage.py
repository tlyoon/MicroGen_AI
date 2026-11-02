"""Advisory source-coverage and semantic-risk triage for authored private lectures.

This module NEVER certifies semantic entailment or uses a language model.
All evidence references are local passage IDs; no source excerpts are exported.
The source identity and exact citation/page/content constraints are enforced
independently by the PR247 authoring gate that calls this module.
"""
from __future__ import annotations

from collections import Counter
import re

class SourceCoverageRiskError(ValueError):
    pass


_GENERAL_WORDS = frozenset("""
a about after again against all also an and another any are as at back based
be because been before being between both but by can change changes check
compare compared comparison consider contain context could data describe
different do does down each even example explain explaining explanation fact
first for form from general get give given has have helps here how if in
include independent into is it its just know later learn make many may might
more must need new no not now of on one only or other our out over own
part particular physical possible present problem process provide question
rather reading remaining result same see should show shows simple
similar so some source state statement step still such supports take than
that the their them then there these they this those through time to
together too two under understand use used useful using value values very
way we what when where which while why will with without work would you
your numerical number numbers lecture student students measurement
measure measurements quantities quantity model concepts concept teaching
scientific scientificity inference presentation observation observations
calculation calculations information important original independent
""".split())


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z]{5,}",value.casefold()))


def _tags(text: str, figure_mentions: list[str]) -> list[str]:
    s=text.casefold()
    found=[]
    if re.search(r"\bexample\s+\d+(?:\.\d+)?\b",s):
        found.append("worked_example")
    if re.search(r"\bquick\s+quiz\s+\d+(?:\.\d+)?\b",s):
        found.append("quick_quiz")
    if re.search(r"^\s*figure\s+\d+(?:\.\d+)+",s) or figure_mentions:
        found.append("figure_reference_or_caption")
    if len(re.findall(r"\b\d+(?:\.\d+)?\b",text))>=2 and re.search(
        r"\b(?:mi|mile|inch|cm|km|m/s|ft|speed|distance|conversion|units?)\b",s):
        found.append("quantitative_unit_context")
    return found or ["exposition"]


def profile_source_coverage(packet: dict, draft: dict) -> dict:
    """Annotate unsupported or uncovered *candidates*, never block valid content.

    The function is called after the existing fail-closed authoring gate.
    It does not read files, send prompts, or assert full coverage.
    """
    if not isinstance(packet,dict) or not isinstance(draft,dict):
        raise SourceCoverageRiskError("Private evidence packet and draft objects required")
    source=packet.get("source_evidence")
    topics=draft.get("topics")
    if (not isinstance(source,list) or not 1<=len(source)<=800
        or not isinstance(topics,list) or not 2<=len(topics)<=60
        or packet.get("publication_allowed") is not False
        or draft.get("publication_allowed") is not False):
        raise SourceCoverageRiskError("Malformed bounded private evidence collection")
    by_id={}
    for item in source:
        if (not isinstance(item,dict) or type(item.get("passage_id")) is not str
            or item["passage_id"] in by_id or type(item.get("source_page")) is not int
            or not isinstance(item.get("text"),str) or not item["text"]
            or not isinstance(item.get("figure_mentions"),list)):
            raise SourceCoverageRiskError("Source passage references must be unambiguous")
        by_id[item["passage_id"]]=item
    cited=Counter()
    topic_rows=[]
    for index,topic in enumerate(topics,1):
        if (not isinstance(topic,dict) or not isinstance(topic.get("source_passage_ids"),list)
            or len(topic["source_passage_ids"]) not in range(1,6)
            or not isinstance(topic.get("narration"),str)
            or not isinstance(topic.get("title"),str)
            or not isinstance(topic.get("bullets"),list)):
            raise SourceCoverageRiskError("Malformed authored topic for triage")
        ids=topic["source_passage_ids"]
        if len(ids)!=len(set(ids)) or any(k not in by_id for k in ids):
            raise SourceCoverageRiskError("Unknown or duplicate cited passage")
        for key in ids:cited[key]+=1
        passages=" ".join(by_id[key]["text"] for key in ids)
        output=topic["title"]+" "+" ".join(topic["bullets"])+" "+topic["narration"]
        source_vocab=_words(passages)
        output_vocab=_words(output)
        # Lexical novelty is a diagnostic ONLY. Paraphrases and pedagogic
        # scaffolding legitimately introduce words absent in the source.
        novelty=sorted((output_vocab-source_vocab)-_GENERAL_WORDS)
        tags=sorted(set(t for key in ids for t in
                        _tags(by_id[key]["text"],by_id[key]["figure_mentions"])))
        topic_rows.append({
            "slide":index,
            "topic_id":topic.get("topic_id"),
            "source_page":topic.get("source_page"),
            "cited_passage_ids":ids,
            "source_context_tags":tags,
            "lexically_new_long_words_sample":novelty[:12],
            "lexical_novelty_is_not_factual_error":True,
            "semantic_claim_entailment_proven":False,
            "source_anchor_already_checked_by_pr247":True,
        })
    inventory=[]
    for item in source:
        passage_id=item["passage_id"]
        labels=_tags(item["text"],item["figure_mentions"])
        inventory.append({
            "passage_id":passage_id,
            "source_page":item["source_page"],
            "category_tags":labels,
            "mentioned_figures":item["figure_mentions"],
            "cited_by_topics":cited[passage_id],
            "unreferenced_advisory":cited[passage_id]==0,
            "qualitative_coverage_unproven":True,
        })
    missing=[row for row in inventory if row["unreferenced_advisory"]]
    high_value=[row for row in inventory
                if any(tag in row["category_tags"] for tag in
                       ("worked_example","quick_quiz","figure_reference_or_caption",
                        "quantitative_unit_context"))]
    important_unlinked=[row for row in high_value if row["unreferenced_advisory"]]
    n=len(inventory)
    # Not a weighted semantic score: every extracted block is an imperfect
    # unit of evidence, and a single sentence can cite several blocks.
    result={
        "schema_version":1,
        "status":"PRIVATE_SOURCE_CONTEXT_COVERAGE_ADVISORY_NOT_SEMANTIC_APPROVAL",
        "source_pdf_sha256":packet.get("source_pdf_sha256"),
        "source_section_id":packet.get("section_id"),
        "source_passages_discovered":n,
        "source_passages_cited":n-len(missing),
        "source_passage_citation_fraction":round((n-len(missing))/n,4),
        "unreferenced_passage_ids":[x["passage_id"] for x in missing],
        "important_context_candidates_count":len(high_value),
        "unreferenced_important_context_candidates":important_unlinked,
        "passage_inventory":inventory,
        "topic_context_audits":topic_rows,
        "topic_count":len(topics),
        "triage_is_advisory":True,
        "uncited_passage_means_omitted_learning_objective":False,
        "lexical_novelty_means_hallucination":False,
        "semantic_entailment_independently_proven":False,
        "academic_completeness_proven":False,
        "formal_voice_authorized":False,
        "publication_allowed":False
    }
    return result
