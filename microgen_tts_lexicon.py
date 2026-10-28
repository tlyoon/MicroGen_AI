"""Versioned, reviewed mathematical pronunciation lexicon.

The lexicon is a conservative verification contract and extension point:
it verifies that the existing approved spoken conversions actually
occur, without blindly rewriting textbook/source narration.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_LEXICON=Path(__file__).parent/"docs"/"tts_pronunciation_lexicon_v1.json"
class LexiconError(ValueError):
    pass

def load_lexicon(path: Path=DEFAULT_LEXICON) -> dict:
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!=1:
        raise LexiconError("Unreviewed lexicon version")
    rules=data.get("reviewed_rules")
    if not isinstance(rules,list) or len(rules)<2:
        raise LexiconError("Reviewed rule set missing")
    ids=set()
    for item in rules:
        ident=item.get("id")
        if not ident or ident in ids or item.get("safety")!="reviewed_conservative":
            raise LexiconError("Unsafe or duplicate pronunciation rule")
        ids.add(ident)
        rx=item.get("source_regex")
        if not isinstance(rx,str) or len(rx)>400:
            raise LexiconError("Malformed reviewed pattern")
        compiled=re.compile(rx,re.I if item.get("case_insensitive") else 0)
        for text in item.get("examples",[]):
            if not compiled.search(text):
                raise LexiconError(f"Positive example missing: {ident}")
        for text in item.get("negative_examples",[]):
            if compiled.search(text):
                raise LexiconError(f"Overbroad match: {ident}")
        if item.get("spoken_template") not in ("{letter_name} {noun}","{cue} see."):
            raise LexiconError("Unknown template requires explicit code review")
    return data

def expected_phrase(rule: dict, match: re.Match) -> str:
    if rule["id"]=="xy-coordinate-compounds":
        return ("why" if match["letter"].lower()=="y" else "ex")+" "+match["noun"].lower()
    if rule["id"]=="sentence_math_cdot":
        return match["cue"]+" see."
    raise LexiconError("Unsupported rule ID")

def verify_spoken_rules(raw: str, spoken: str, *, lexicon: dict | None=None) -> list[dict]:
    """Return contextual review flags when a known-safe conversion drifts."""
    data=lexicon if lexicon is not None else load_lexicon()
    failures=[]
    for rule in data["reviewed_rules"]:
        compiled=re.compile(rule["source_regex"],re.I if rule.get("case_insensitive") else 0)
        for match in compiled.finditer(raw):
            phrase=expected_phrase(rule,match)
            if phrase.lower() not in spoken.lower():
                failures.append({"rule":rule["id"],"source":match.group(),
                                 "expected":phrase,"start":match.start()})
    return failures

def check_lexicon_slides(slides: list[dict], normalize: Callable[[str],str],
                         *, lexicon: dict | None=None) -> list[dict]:
    data=lexicon if lexicon is not None else load_lexicon()
    issues=[]
    for number,item in enumerate(slides,1):
        raw=str(item.get("tts_text") or item.get("narration") or "")
        normalized=normalize(raw)
        for finding in verify_spoken_rules(raw,normalized,lexicon=data):
            issues.append({"slide":item.get("slide",number),**finding})
    return issues
