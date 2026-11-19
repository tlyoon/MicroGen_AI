"""Production scientific/acoustic QA severity contract (2026-11-18).

Educational meaning matters more than a literal transcript. Only fixed,
auditable equivalents are auto-canonicalized; other plausible paraphrases
must be marked advisory by a source-grounded reviewer, NEVER guessed.
Mathematical operators, sign, quantity, variable, negation, units and
science claims must not silently change. Fail closed when uncertain.
"""
from __future__ import annotations
import re
import unicodedata

CONTRACT_VERSION="SOURCE_MEANING_OVER_LITERAL_SPEECH_V1"

# Exact equivalent terms, not arbitrary phonetic neighbors or numerically
# plausible substitutions. Longer phrases first to avoid partial matches.
SPOKEN_EQUIVALENTS=(
    ("is equal to", "equals"),
    ("equal to", "equals"),
    ("multiplied by", "multiply by"),
    ("multiplying by", "multiply by"),
    ("dividing by", "divide by"),
    ("divided by", "divide by"),
    ("metres", "meters"),
    ("metre", "meter"),
    ("centimetres", "centimeters"),
    ("centimetre", "centimeter"),
    ("kilometres", "kilometers"),
    ("kilometre", "kilometer"),
)
# These are permissible changes only when the WHOLE reviewed scientific
# quote can be matched, including all scientific words and numbers.
NONTECHNICAL_EQUIVALENTS=(
    ("we can see that", "we observe that"),
    ("we see that", "we observe that"),
    ("therefore", "thus"),
    ("in this example", "for this example"),
    ("the diagram shows", "the figure shows"),
)


def _replace_phrase(text:str,original:str,replacement:str)->str:
    return re.sub(r"(?<![a-z0-9])"+re.escape(original)+r"(?![a-z0-9])",
                  replacement,text)


def canonical_equivalent_text(value:str,*,nontechnical:bool=False)->str:
    """Preserve mathematical punctuation/signs, digits and entire word identities."""
    if not isinstance(value,str):
        raise TypeError("QA must compare literal source and observed text")
    s=unicodedata.normalize("NFKC",value).casefold()
    s=re.sub(r"\s+"," ",s).strip()
    for before,after in SPOKEN_EQUIVALENTS:
        s=_replace_phrase(s,before,after)
    if nontechnical:
        for before,after in NONTECHNICAL_EQUIVALENTS:
            s=_replace_phrase(s,before,after)
    # Ignore only terminal punctuation/casing; never minus, plus, =, /,
    # decimal points inside numbers, brackets, or other math symbols.
    s=s.strip(" .,:;!?")
    s=re.sub(r"\s+"," ",s)
    return s


def provably_minor_scientific_issue(issue:dict,source:str,
                                    observed_slide:str,observed_narration:str)->bool:
    """One strictly bounded, independently source-cited semantic equivalent."""
    if (not isinstance(issue,dict) or issue.get("field") not in
            ("slide","narration")):
        return False
    observed=issue.get("observed_quote")
    cited=issue.get("source_quote")
    if (not isinstance(observed,str) or not isinstance(cited,str)
            or len(observed)<12 or len(cited)<12
            or len(observed)>350 or len(cited)>350):
        return False
    field_text=(observed_slide if issue["field"]=="slide"
                else observed_narration)
    if (observed not in field_text or cited not in source):
        return False
    # Full source-quoted statement must be equivalent. Nontechnical
    # terminology variation is tolerable; physics/science logic is not.
    left=canonical_equivalent_text(observed,nontechnical=True)
    right=canonical_equivalent_text(cited,nontechnical=True)
    return bool(left) and left==right and observed!=cited


def reclassify_proven_minor_scientific_issues(rows:list[dict],
               source:list[str],slide_text:list[str],
               narrations:list[str])->tuple[list[dict],list[int]]:
    """Downgrade only wholly proven-equivalent error rows to advisories.

    All original quotes retained. Any mixed or ungrounded row stays ERROR,
    ensuring unsupported scientific corrections never become passes.
    """
    if (not isinstance(rows,list) or
            not(len(rows)==len(slide_text)==len(narrations))
            or not isinstance(source,list)):
        raise ValueError("Untrusted source-bound science QA inputs")
    corpus="\n".join(source)
    revised=[]
    downgraded=[]
    for position,row in enumerate(rows):
        candidate=dict(row)
        if (row["status"]=="error" and row.get("issues")
                and all(provably_minor_scientific_issue(
                    issue,corpus,slide_text[position],narrations[position])
                    for issue in row["issues"])):
            candidate["status"]="advisory"
            downgraded.append(position+1)
        revised.append(candidate)
    return revised,downgraded
