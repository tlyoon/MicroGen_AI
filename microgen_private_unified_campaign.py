"""Atomic PRIVATE combined source-coverage and source-scientific regression.

Runs existing source-packet and typed-math verifiers, not any language model.
All receipts are saved privately and contain source IDs/hashes/counts only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_private_authoring_gate import _safe_output
from microgen_private_cross_section_coverage import (
    _read_private_json, audit_private_section_campaign)
from microgen_private_multisection_scientific_claim_audit import (
    audit_private_science_campaign)


class UnifiedPrivateCampaignError(ValueError):
    pass


def audit_unified_private_campaign(cases:list,output:Path)->dict:
    """All-or-nothing verification across matching private authoring and stages.

    Cases: section_id, source_pdf, private_packet, private_draft, stage.
    Both established validators run against exactly the same immutable source
    path/section ID, and we verify their independent identity receipts agree.
    """
    if not isinstance(cases,list) or not 1<=len(cases)<=12:
        raise UnifiedPrivateCampaignError("One to twelve source-bound stages required")
    dest=Path(output)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,130}",dest.name):
        raise UnifiedPrivateCampaignError("Bounded private output name required")
    coverage_cases=[]
    science_cases=[]
    before={}
    protected_stages=[]
    seen=set()
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={
            "section_id","source_pdf","private_packet","private_draft","stage"}):
            raise UnifiedPrivateCampaignError("Explicit source, original response and stage required")
        section=case["section_id"]
        if (not isinstance(section,str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,30}",section)
            or section in seen):
            raise UnifiedPrivateCampaignError("Unique section IDs required")
        seen.add(section)
        paths=[Path(case[k]) for k in (
            "source_pdf","private_packet","private_draft")]
        stage=Path(case["stage"])
        if not stage.is_dir() or stage.is_symlink():
            raise UnifiedPrivateCampaignError("Private stage missing")
        protected_stages.append(stage.resolve(strict=True))
        paths.extend([stage/k for k in (
            "source.pdf","narration.json","plan.json","contract.json")])
        for source in paths:
            if source.is_symlink() or not source.is_file():
                raise UnifiedPrivateCampaignError("Private source, packet or stage file missing")
            actual=source.resolve(strict=True)
            digest=sha_file(actual)
            if actual in before and before[actual]!=digest:
                raise UnifiedPrivateCampaignError("Input changed during campaign preparation")
            before[actual]=digest
        original=paths[0].resolve(strict=True)
        if sha_file(stage/"source.pdf")!=before[original]:
            raise UnifiedPrivateCampaignError("Private authored stage source differs from actual original")
        # Freeze image source evidence as well, including files the scientific
        # checker will use to re-render and hash-compare original source pixels.
        manifest=_read_private_json(stage/"contract.json")
        figures=manifest.get("figures",[])
        if not isinstance(figures,list) or len(figures)>60:
            raise UnifiedPrivateCampaignError("Invalid figure inventory")
        for spec in figures:
            if not isinstance(spec,dict) or not isinstance(spec.get("filename"),str):
                raise UnifiedPrivateCampaignError("Unsafe figure record")
            name=spec["filename"]
            if Path(name).name!=name or name in (".",".."):
                raise UnifiedPrivateCampaignError("Unsafe figure name")
            figure=stage/name
            if figure.is_symlink() or not figure.is_file():
                raise UnifiedPrivateCampaignError("Protected source figure not found")
            resolved=figure.resolve(strict=True)
            before[resolved]=sha_file(resolved)
        coverage_cases.append({k:case[k] for k in (
            "section_id","source_pdf","private_packet","private_draft")})
        science_cases.append({
            "section_id":section,"original_pdf":case["source_pdf"],
            "stage":case["stage"]})
    dest=_safe_output(dest,Path(cases[0]["source_pdf"]))
    for path in [*before.keys(),*protected_stages]:
        if dest==path or dest in path.parents or path in dest.parents:
            raise UnifiedPrivateCampaignError("Destination collides with protected source input")
    temp=Path(tempfile.mkdtemp(prefix=".microgen-unified-private-",dir=dest.parent))
    try:
        coverage=audit_private_section_campaign(
            coverage_cases,temp/"coverage")
        science=audit_private_science_campaign(
            science_cases,temp/"science")
        if (coverage["section_count"]!=len(cases)
            or science["section_count"]!=len(cases)):
            raise UnifiedPrivateCampaignError("Inconsistent section inventory")
        coverage_rows={x["section_id"]:x for x in coverage["section_records"]}
        science_rows={x["section_id"]:x for x in science["section_records"]}
        if set(coverage_rows)!=set(science_rows) or set(coverage_rows)!=seen:
            raise UnifiedPrivateCampaignError("Source and science section identifiers do not agree")
        match=[]
        for section in sorted(seen):
            a,b=coverage_rows[section],science_rows[section]
            if (a["source_pdf_sha256"]!=b["original_pdf_sha256"]
                or a["authored_topics_verified"]!=b["original_source_topic_count"]):
                raise UnifiedPrivateCampaignError(
                    "Original source or topic inventory mismatch between independent gates")
            match.append({"section_id":section,
                "original_source_sha256":a["source_pdf_sha256"],
                "source_passages_discovered":a["source_passages_discovered"],
                "source_passages_linked":a["source_passages_cited"],
                "authored_topics_verified":a["authored_topics_verified"],
                "high_interest_uncited_advisory":len(a["high_interest_uncited"]),
                "verified_source_figures":b["original_source_raster_figures_checked"],
                "verified_source_vector_equations":b["original_source_vector_equation_crops_checked"],
                "verified_source_typed_math":b["original_source_typed_math_claims_recalculated"],
                "verified_source_significant_figure_claims":b["original_source_significant_figure_claims_verified"],
                "verified_source_rounding_examples":b["original_source_rounding_examples_verified"],
                "verified_dimensional_relations":b["typed_dimensional_equalities_checked"],
                "verified_si_relations":b["typed_si_unit_relations_checked"],
                "verified_spoken_si_equalities":b["automatically_checked_spoken_unit_equalities"],
                "verified_source_spoken_comparison":b[
                    "source_confirmed_spoken_speed_limit_conclusions_checked"]})
        if any(sha_file(path)!=digest for path,digest in before.items()):
            raise UnifiedPrivateCampaignError("Original source or authored stage changed during campaign")
        report={
            "schema_version":1,
            "status":"UNIFIED_PRIVATE_SOURCE_AND_SCIENTIFIC_GATES_PASSED_WITH_LIMITS",
            "section_count":len(match),
            "sections":match,
            "coverage_receipt_sha256":sha_file(
                temp/"coverage"/"multisection_private_coverage_receipt.json"),
            "science_receipt_sha256":sha_file(
                temp/"science"/"multisection_private_science_receipt.json"),
            "original_sources_unchanged":True,
            "textbook_or_narration_excerpts_in_any_receipt":False,
            "locally_installed_language_model_invoked":False,
            "paid_provider_api_calls":0,
            "academic_completeness_proven":False,
            "all_physics_semantics_proven":False,
            "formal_voice_authorized":False,
            "publication_allowed":False
        }
        (temp/"unified_private_campaign_receipt.json").write_text(
            json.dumps(report,indent=2),encoding="utf8")
        if dest.exists() or dest.is_symlink():
            raise UnifiedPrivateCampaignError("Destination appeared during validation")
        os.rename(temp,dest)
        return report
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-manifest",type=Path,required=True)
    p.add_argument("--new-private-output",type=Path,required=True)
    opt=p.parse_args(argv)
    manifest=_read_private_json(opt.private_manifest)
    result=audit_unified_private_campaign(manifest.get("cases"),opt.new_private_output)
    print(json.dumps({"status":result["status"],
        "section_count":result["section_count"],
        "source_passages":sum(r["source_passages_discovered"] for r in result["sections"]),
        "source_linked":sum(r["source_passages_linked"] for r in result["sections"]),
        "verified_figures":sum(r["verified_source_figures"] for r in result["sections"]),
        "typed_math":sum(r["verified_source_typed_math"] for r in result["sections"]),
        "publication_allowed":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
