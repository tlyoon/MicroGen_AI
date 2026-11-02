"""Optional source-bounded dimensional equation consistency QA.

Safely evaluates dimensions of typed formulas using L/M/T exponents, not Python
eval. It checks necessary algebraic consistency and source citation, NOT
physical derivation correctness or complete textbook content.
"""
from __future__ import annotations
import ast
from pathlib import Path
import re

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import clean
from microgen_source_passage_discovery import discover_passages


class DimensionProofError(ValueError):
    pass


ZERO=(0,0,0)
BASE={"L":(1,0,0),"M":(0,1,0),"T":(0,0,1)}


def _combine(a,b,sign=1):
    result=tuple(x+sign*y for x,y in zip(a,b))
    if any(abs(v)>30 for v in result):
        raise DimensionProofError("Dimension exponent outside bounded range")
    return result


def _power_number(node):
    if isinstance(node,ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
        if isinstance(node.operand,ast.Constant) and type(node.operand.value) is int:
            return -node.operand.value
    raise DimensionProofError("Powers must be explicit bounded integer constants")


def _dimension_tree(node,variables):
    if isinstance(node,ast.Expression):
        return _dimension_tree(node.body,variables)
    if isinstance(node,ast.Name):
        if node.id not in variables:
            raise DimensionProofError("Unknown variable or base dimension in expression")
        return variables[node.id]
    if isinstance(node,ast.Constant) and type(node.value) in (int,float):
        if not -1e8<float(node.value)<1e8:
            raise DimensionProofError("Unbounded coefficient")
        return ZERO
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        return _dimension_tree(node.operand,variables)
    if isinstance(node,ast.BinOp):
        if isinstance(node.op,ast.Pow):
            p=_power_number(node.right)
            if not -8<=p<=8:
                raise DimensionProofError("Unbounded power")
            lhs=_dimension_tree(node.left,variables)
            return _combine(ZERO,tuple(p*x for x in lhs))
        if isinstance(node.op,(ast.Div,ast.Mult,ast.Add,ast.Sub)):
            if (isinstance(node.op,ast.Div)
                and isinstance(node.right,ast.Constant)
                and type(node.right.value) in (int,float)
                and node.right.value==0):
                raise DimensionProofError("Division by zero")
            lhs=_dimension_tree(node.left,variables)
            rhs=_dimension_tree(node.right,variables)
            if isinstance(node.op,ast.Mult):return _combine(lhs,rhs)
            if isinstance(node.op,ast.Div):return _combine(lhs,rhs,-1)
            if lhs!=rhs:
                raise DimensionProofError("Adding or subtracting incompatible dimensions")
            return lhs
    raise DimensionProofError("Unsafe or unsupported dimensional expression")


def parse_dimension(expression,variables):
    if (not isinstance(expression,str) or not 1<=len(expression)<=140
        or not expression.isascii()):
        raise DimensionProofError("Bounded ASCII expression required")
    try:
        tree=ast.parse(expression,mode="eval")
    except (ValueError,SyntaxError) as e:
        raise DimensionProofError("Invalid expression") from e
    if sum(1 for _ in ast.walk(tree))>40:
        raise DimensionProofError("Excessively complex expression")
    return _dimension_tree(tree,variables)


def _variable_definitions(declarations):
    if (not isinstance(declarations,dict) or not 1<=len(declarations)<=15):
        raise DimensionProofError("Bounded variable definitions required")
    result={}
    for key,expression in declarations.items():
        if (not isinstance(key,str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,11}",key)):
            raise DimensionProofError("Invalid variable symbol")
        result[key]=parse_dimension(expression,BASE)
    return result


def check_source_dimensional_relations(source:Path,manifest:dict,narration:dict):
    """Check opt-in dimension claims and their PDF section source anchors."""
    claims=manifest.get("source_dimension_claims",[])
    if not isinstance(claims,list) or len(claims)>30:
        raise DimensionProofError("Invalid dimension claim collection")
    if not claims:
        return {}
    source=Path(source)
    original_sha=sha_file(source)
    if manifest.get("source_pdf_sha256")!=original_sha:
        raise DimensionProofError("Typed formula not locked to original PDF identity")
    try:
        evidence=discover_passages(source,manifest["start_marker"],
                 manifest.get("next_section_marker"),
                 end_of_pdf=manifest.get("end_of_pdf") is True)
    except (KeyError,ValueError,TypeError) as e:
        raise DimensionProofError("Source section evidence cannot be reconstructed") from e
    by_id={p["passage_id"]:p for p in evidence["passages"]}
    slides=narration.get("slides")
    if not isinstance(slides,list):
        raise DimensionProofError("Original narration slide inventory missing")
    found={}
    for claim in claims:
        if not isinstance(claim,dict):
            raise DimensionProofError("Malformed dimensional claim")
        slide=claim.get("slide")
        page=claim.get("source_page")
        ids=claim.get("source_passage_ids")
        anchor=claim.get("source_anchor")
        terms=claim.get("required_source_terms")
        if (type(slide) is not int or not 1<=slide<=len(slides)
            or slide in found or type(page) is not int
            or page!=slides[slide-1].get("source_page")
            or not isinstance(ids,list) or not 1<=len(ids)<=5
            or len(ids)!=len(set(ids))
            or any(type(k) is not str or k not in by_id
                   or by_id[k]["source_page"]!=page for k in ids)
            or not isinstance(anchor,str) or not 8<=len(anchor)<=160
            or not isinstance(terms,list) or not 2<=len(terms)<=5
            or any(type(t) is not str or not 3<=len(t)<=50 for t in terms)):
            raise DimensionProofError("Typed relation not tied to an unambiguous slide and source")
        text=" ".join(by_id[k]["text"] for k in ids)
        if (clean(anchor) not in clean(text)
            or any(clean(t) not in clean(text) for t in terms)):
            raise DimensionProofError("Typed relation missing bounded source evidence")
        variables=_variable_definitions(claim.get("variables"))
        lhs=parse_dimension(claim.get("lhs"),variables)
        rhs=parse_dimension(claim.get("rhs"),variables)
        if lhs!=rhs:
            raise DimensionProofError(f"Slide {slide}: incompatible dimensions across equation")
        found[slide]={
            "source_page":page,"source_passage_ids":ids,
            "lhs":claim["lhs"],"rhs":claim["rhs"],
            "dimensions_L_M_T":list(lhs),
            "dimensionally_consistent":True,
            "source_anchor_literal_verified":True,
            "physical_relationship_semantically_proven":False,
            "dimensionless_coefficient_determined":False,
            "independent_complete_academic_certification":False,
            "publication_allowed":False}
    if sha_file(source)!=original_sha:
        raise DimensionProofError("Original source changed during dimensional check")
    return found
