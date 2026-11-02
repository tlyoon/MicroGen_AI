"""Private cross-subsection source-evidence audit, without media regeneration.

Rebuild original PDF passage identity for every case. Revalidate writer drafts
against the existing PR247 gate, recompute PR253 advisory coverage and report
only hashes/counts and source-passage IDs — no source text, narration or figures.
No language model, browser, provider API, TTS, local inference or publication.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from microgen_portable_private_authoring_gate import (
    AuthoringGateError, _safe_output, _validate_draft,
    build_authoring_packet, canonical_hash)
from microgen_portable_semantic_coverage_triage import profile_source_coverage
from microgen_pronunciation_closed_loop import sha_file


class MultiSectionEvidenceError(ValueError):
    pass


def _read_private_json(p: Path) -> dict:
    if p.is_symlink() or not p.is_file() or not 10<=p.stat().st_size<=900_000:
        raise MultiSectionEvidenceError("Bounded real private JSON file required")
    try:
        data=json.loads(p.read_text(encoding="utf8"))
    except (ValueError, UnicodeError) as e:
        raise MultiSectionEvidenceError("Malformed source-bound private JSON") from e
    if not isinstance(data,dict):
        raise MultiSectionEvidenceError("Private source evidence must be a JSON object")
    return data


def audit_private_section_campaign(cases:list, output:Path)->dict:
    """Validate 1–12 real sections; make fresh receipt only when ALL succeed."""
    output=Path(output)
    if not isinstance(cases,list) or not 1<=len(cases)<=12:
        raise MultiSectionEvidenceError("Expected one to twelve independent source cases")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+",output.name):
        raise MultiSectionEvidenceError("Unsafe output name")
    seen=set()
    rows=[]
    frozen={}
    inputs=[]
    for case in cases:
        if not isinstance(case,dict) or set(case)!={
            "section_id","source_pdf","private_packet","private_draft"}:
            raise MultiSectionEvidenceError("Complete private case fields required")
        section=case["section_id"]
        if (not isinstance(section,str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,30}",section)
            or section in seen):
            raise MultiSectionEvidenceError("Unique bounded section ID required")
        seen.add(section)
        src=Path(case["source_pdf"]);packpath=Path(case["private_packet"])
        draftpath=Path(case["private_draft"])
        if src.is_symlink() or not src.is_file():
            raise MultiSectionEvidenceError("Read-only original source PDF required")
        for path in (src,packpath,draftpath):
            before=sha_file(path)
            frozen[str(path.resolve(strict=True))]=before
            inputs.append(path.resolve(strict=True))
        packet=_read_private_json(packpath)
        draft=_read_private_json(draftpath)
        if packet.get("section_id")!=section or draft.get("section_id")!=section:
            raise MultiSectionEvidenceError("Mismatched source and authored section IDs")
        original=sha_file(src)
        if (packet.get("source_pdf_sha256")!=original
            or draft.get("source_pdf_sha256")!=original
            or draft.get("packet_sha256")!=canonical_hash(packet)
            or packet.get("publication_allowed") is not False
            or draft.get("publication_allowed") is not False):
            raise MultiSectionEvidenceError("Original source packet and model draft are not SHA-linked")
        fresh=build_authoring_packet(src,packet.get("start_marker"),
                packet.get("next_section_marker"),
                end_of_pdf=packet.get("end_of_pdf") is True,
                section_id=section)
        if canonical_hash(fresh)!=canonical_hash(packet):
            raise MultiSectionEvidenceError("Source packet does not match original PDF")
        # The established PR247 canonical validator handles word/number/passage
        # evidence, and can refuse a false scientific numeric claim. We do not
        # claim its lexical checks are complete semantic entailment.
        accepted,_qa=_validate_draft(fresh,draft,src)
        coverage=profile_source_coverage(fresh,draft)
        if len(accepted)!=coverage["topic_count"]:
            raise MultiSectionEvidenceError("Topic inventory drift")
        rows.append({
            "section_id":section,
            "source_pdf_sha256":original,
            "private_packet_sha256":canonical_hash(packet),
            "private_draft_sha256":canonical_hash(draft),
            "authored_topics_verified":coverage["topic_count"],
            "source_passages_discovered":coverage["source_passages_discovered"],
            "source_passages_cited":coverage["source_passages_cited"],
            "source_passage_citation_fraction":coverage["source_passage_citation_fraction"],
            "unreferenced_passage_ids":coverage["unreferenced_passage_ids"],
            "high_interest_uncited":[
                {"passage_id":x["passage_id"],"source_page":x["source_page"],
                 "category_tags":x["category_tags"]}
                for x in coverage["unreferenced_important_context_candidates"]],
            "full_source_semantic_entailment_verified":False,
            "complete_academic_coverage_proven":False,
        })
    # Make no receipt at all on a single failed section; never write into any
    # original source or the source-containing cloud Drive hierarchy.
    source_reference=Path(cases[0]["source_pdf"])
    dest=_safe_output(output,source_reference)
    if any(dest==v or dest in v.parents or v in dest.parents for v in inputs):
        raise MultiSectionEvidenceError("Private output cannot modify input hierarchy")
    record={
        "schema_version":1,
        "status":"MULTISECTION_ORIGINAL_SOURCE_REVALIDATED_COVERAGE_ADVISORY",
        "section_count":len(rows),
        "section_records":rows,
        "source_passages_discovered_total":sum(r["source_passages_discovered"] for r in rows),
        "source_passages_cited_total":sum(r["source_passages_cited"] for r in rows),
        "high_interest_uncited_total":sum(len(r["high_interest_uncited"]) for r in rows),
        "no_source_or_authored_text_in_receipt":True,
        "all_source_documents_unchanged":True,
        "provider_or_local_language_model_invoked":False,
        "academic_completeness_proven":False,
        "publication_allowed":False
    }
    if any(sha_file(Path(path))!=sha for path,sha in frozen.items()):
        raise MultiSectionEvidenceError("An original source/input changed during audit")
    temporary=Path(tempfile.mkdtemp(prefix=".microgen-cross-section-",dir=dest.parent))
    try:
        (temporary/"multisection_private_coverage_receipt.json").write_text(
            json.dumps(record,indent=2),encoding="utf8")
        if dest.exists():raise MultiSectionEvidenceError("Destination appeared during validation")
        os.rename(temporary,dest)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return record


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--private-case-manifest",type=Path,required=True)
    cli.add_argument("--new-private-output",type=Path,required=True)
    a=cli.parse_args(argv)
    data=_read_private_json(a.private_case_manifest)
    result=audit_private_section_campaign(data.get("cases"),a.new_private_output)
    print(json.dumps({"status":result["status"],
        "section_count":result["section_count"],
        "source_passages_discovered_total":result["source_passages_discovered_total"],
        "source_passages_cited_total":result["source_passages_cited_total"],
        "high_interest_uncited_total":result["high_interest_uncited_total"],
        "publication_allowed":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
