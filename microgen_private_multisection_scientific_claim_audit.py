"""Read-only cross-section SCIENTIFIC CLAIM proofs for private lecture stages.

Revalidates original on-disk source PDFs against stage copies, section
contracts and narration. Computes independent L/M/T, typed SI and definite
narrative comparison checks; does not regenerate images, audio or video.
No provider/API/local language-model calls; no source content in receipts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from microgen_portable_private_authoring_gate import _safe_output
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import audit_portable_contract
from microgen_portable_source_dimensional_relations import check_source_dimensional_relations
from microgen_portable_source_unit_conversions import verified_source_unit_conversions
from microgen_portable_narration_unit_equivalence import check_narrated_unit_equivalences
from microgen_portable_scientific_comparison_polarity import checked_source_comparison_narration
from microgen_private_original_figure_math_reaudit import audit_original_figure_math
from microgen_private_source_significant_figures import verify_source_significant_figure_claims
from microgen_private_source_rounding_examples import verified_original_source_rounding


class MultiSectionScientificEvidenceError(ValueError):
    pass


def audit_private_science_campaign(cases:list,output:Path)->dict:
    if not isinstance(cases,list) or not 1<=len(cases)<=12:
        raise MultiSectionScientificEvidenceError("Expected 1 to 12 private source stages")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,130}",Path(output).name):
        raise MultiSectionScientificEvidenceError("Unsafe output basename")
    ids=set()
    freeze={}
    rows=[]
    protected=[]
    for c in cases:
        if (not isinstance(c,dict) or set(c)!={"section_id","original_pdf","stage"}
            or not isinstance(c.get("section_id"),str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,30}",c["section_id"])
            or c["section_id"] in ids):
            raise MultiSectionScientificEvidenceError("Malformed/duplicate section case")
        ids.add(c["section_id"])
        original=Path(c["original_pdf"])
        stage=Path(c["stage"])
        if (not original.is_file() or original.is_symlink()
            or not stage.is_dir() or stage.is_symlink()):
            raise MultiSectionScientificEvidenceError("Real immutable original and private stage required")
        paths=[original,stage/"source.pdf",stage/"narration.json",
               stage/"plan.json",stage/"contract.json"]
        for path in paths:
            if path.is_symlink() or not path.is_file() or path.stat().st_size>15_000_000:
                # Original PDFs must be bounded and all inputs nonsymlinked.
                raise MultiSectionScientificEvidenceError("Unsafe/missing original source or stage files")
            resolved=path.resolve(strict=True)
            if str(resolved) in freeze and freeze[str(resolved)]!=sha_file(path):
                raise MultiSectionScientificEvidenceError("Input changed while selected")
            freeze[str(resolved)]=sha_file(path)
            protected.append(resolved)
        if sha_file(original)!=sha_file(stage/"source.pdf"):
            raise MultiSectionScientificEvidenceError("Stage source PDF differs from original authoritative PDF")
        try:
            manifest=json.loads((stage/"contract.json").read_text(encoding="utf8"))
            narration=json.loads((stage/"narration.json").read_text(encoding="utf8"))
        except (UnicodeError,ValueError) as ex:
            raise MultiSectionScientificEvidenceError("Private stage JSON malformed") from ex
        if (not isinstance(manifest,dict) or not isinstance(narration,dict)
            or manifest.get("section_id")!=c["section_id"]
            or manifest.get("source_pdf_sha256")!=sha_file(original)
            or manifest.get("publication_allowed") is not False
            or narration.get("publication_allowed") is not False):
            raise MultiSectionScientificEvidenceError("Source lineage, section ID or nonpublication invalid")
        academic=audit_portable_contract(stage/"source.pdf",stage/"narration.json",
                                         stage/"plan.json",stage/"contract.json")
        dimensions=check_source_dimensional_relations(original,manifest,narration)
        si=verified_source_unit_conversions(original,manifest,narration)
        narrated=check_narrated_unit_equivalences(narration)
        polarity=checked_source_comparison_narration(manifest,narration,si)
        original_math=audit_original_figure_math(stage,original,manifest,narration)
        sigfig=verify_source_significant_figure_claims(original,manifest,narration)
        rounding=verified_original_source_rounding(original,manifest,narration)
        for spec in manifest.get("figures",[]):
            original_figure=(stage/spec["filename"]).resolve(strict=True)
            freeze[str(original_figure)]=sha_file(original_figure)
            protected.append(original_figure)
        rows.append({
            "section_id":c["section_id"],
            "original_pdf_sha256":sha_file(original),
            "contract_sha256":sha_file(stage/"contract.json"),
            "narration_sha256":sha_file(stage/"narration.json"),
            "original_source_topic_count":academic["topic_count"],
            "typed_dimensional_equalities_checked":len(dimensions),
            "typed_si_unit_relations_checked":len(si),
            "automatically_checked_spoken_unit_equalities":sum(len(x) for x in narrated.values()),
            "source_confirmed_spoken_speed_limit_conclusions_checked":len(polarity),
            "original_source_raster_figures_checked":original_math["original_source_raster_figures_checked"],
            "original_source_vector_equation_crops_checked":original_math["source_vector_equation_crops_checked"],
            "original_source_typed_math_claims_recalculated":original_math["independently_recalculated_source_typed_math_claims"],
            "original_source_significant_figure_claims_verified":len(sigfig),
            "original_source_rounding_examples_verified":sum(map(len,rounding.values())),
            "original_source_geometry_and_math_pipeline_checked":True,
            "complete_scientific_entailment_verified":False,
            "complete_academic_coverage_proven":False,
        })
    dest=_safe_output(Path(output),Path(cases[0]["original_pdf"]))
    for inp in protected:
        if dest==inp or dest in inp.parents or inp in dest.parents:
            raise MultiSectionScientificEvidenceError("Output must not modify input/source hierarchy")
    report={
        "schema_version":1,
        "status":"PRIVATE_MULTISECTION_SCIENTIFIC_CLAIM_CHECKS_PASSED_NOT_COMPLETE_SCIENCE",
        "section_count":len(rows),
        "section_records":rows,
        "typed_dimensional_equalities_checked":sum(x["typed_dimensional_equalities_checked"] for x in rows),
        "typed_si_unit_relations_checked":sum(x["typed_si_unit_relations_checked"] for x in rows),
        "automatically_checked_spoken_unit_equalities":sum(x["automatically_checked_spoken_unit_equalities"] for x in rows),
        "source_confirmed_spoken_speed_limit_conclusions_checked":sum(x["source_confirmed_spoken_speed_limit_conclusions_checked"] for x in rows),
        "original_source_raster_figures_checked":sum(x["original_source_raster_figures_checked"] for x in rows),
        "original_source_vector_equation_crops_checked":sum(x["original_source_vector_equation_crops_checked"] for x in rows),
        "original_source_typed_math_claims_recalculated":sum(x["original_source_typed_math_claims_recalculated"] for x in rows),
        "original_source_significant_figure_claims_verified":sum(x["original_source_significant_figure_claims_verified"] for x in rows),
        "original_source_rounding_examples_verified":sum(x["original_source_rounding_examples_verified"] for x in rows),
        "source_or_narration_excerpts_in_report":False,
        "all_original_inputs_unchanged":True,
        "provider_or_local_language_model_invoked":False,
        "complete_scientific_entailment_verified":False,
        "formal_voice_authorized":False,
        "publication_allowed":False,
    }
    if any(sha_file(Path(q))!=h for q,h in freeze.items()):
        raise MultiSectionScientificEvidenceError("Inputs mutated during scientific audit")
    tmp=Path(tempfile.mkdtemp(prefix=".microgen-science-audit-",dir=dest.parent))
    try:
        (tmp/"multisection_private_science_receipt.json").write_text(
            json.dumps(report,indent=2),encoding="utf8")
        if dest.exists() or dest.is_symlink():
            raise MultiSectionScientificEvidenceError("Destination appeared during audit")
        os.rename(tmp,dest)
    finally:
        if tmp.exists():shutil.rmtree(tmp)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-manifest",required=True,type=Path)
    parser.add_argument("--new-private-output",required=True,type=Path)
    opts=parser.parse_args(argv)
    f=opts.private_manifest
    if f.is_symlink() or not f.is_file() or f.stat().st_size>250_000:
        raise MultiSectionScientificEvidenceError("Bounded private manifest required")
    obj=json.loads(f.read_text(encoding="utf8"))
    res=audit_private_science_campaign(obj["cases"],opts.new_private_output)
    print(json.dumps({
        "status":res["status"],"sections":res["section_count"],
        "dimension_checks":res["typed_dimensional_equalities_checked"],
        "si_checks":res["typed_si_unit_relations_checked"],
        "spoken_unit_checks":res["automatically_checked_spoken_unit_equalities"],
        "source_polarity_checks":res["source_confirmed_spoken_speed_limit_conclusions_checked"],
        "original_figures_checked":res["original_source_raster_figures_checked"],
        "original_vector_equations_checked":res["original_source_vector_equation_crops_checked"],
        "original_typed_math_checks":res["original_source_typed_math_claims_recalculated"],
        "source_significant_figure_checks":res["original_source_significant_figure_claims_verified"],
        "source_rounding_example_checks":res["original_source_rounding_examples_verified"],
        "publication_allowed":False
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
