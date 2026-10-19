"""Conservative, offline preflight for mathematical TTS text.

This module does not edit narration. It blocks a small set of unambiguous
unrendered scientific notation rather than guessing how to speak it.
Additional pronunciations require reviewed rules and regression examples.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

# Only math lexemes are eligible. Keep titles, names and 'c. 1900' intact.
_C_SENTENCE = re.compile(r"(?<![A-Za-z])c\.(?=\s+[A-Z]|$)")
_MATH_CUE = re.compile(
    r"\b(?:at|point|limit|function|variable|coefficient|constant|parameter|"
    r"approaches?|approaching|tends?|converges?|evaluat\w*|derivative|"
    r"integral|equals?|root|value|continuous|continuity)\b", re.I
)
_TEX_COMMAND = re.compile(r"\\[A-Za-z]+")
_UNSAFE_SUBSCRIPT = re.compile(r"\b[A-Za-z]_(?:\d+|[A-Za-z])\b")


@dataclass(frozen=True)
class PronunciationIssue:
    code: str
    start: int
    snippet: str
    reason: str


class PronunciationPreflightError(ValueError):
    """Input requires explicit mathematical speech interpretation."""


def find_issues(raw: str, spoken: str) -> list[PronunciationIssue]:
    """Inspect normalized spoken input; offsets refer to *spoken*, not source."""
    issues: list[PronunciationIssue] = []
    for match in _C_SENTENCE.finditer(spoken):
        # Non-mathematical examples and historical 'c. 1900' are deliberately
        # not changed; the cue must be near the token in the same clause.
        prior = spoken[max(0, match.start() - 70):match.start()]
        prior = re.split(r"[.!?;]\s*", prior)[-1]
        if _MATH_CUE.search(prior):
            issues.append(PronunciationIssue(
                "ambiguous_math_c_period", match.start(),
                spoken[max(0, match.start()-35):match.end()+35],
                "Mathematical c. may be spoken as circa; provide explicit letter-C speech."
            ))
    for token in _TEX_COMMAND.finditer(spoken):
        issues.append(PronunciationIssue(
            "raw_latex_command", token.start(), token.group(),
            "Unrendered LaTeX command requires an explicit spoken form."
        ))
    for token in _UNSAFE_SUBSCRIPT.finditer(spoken):
        issues.append(PronunciationIssue(
            "raw_subscript", token.start(), token.group(),
            "Subscript notation must be converted to reviewed spoken text."
        ))
    return issues


def require_safe_speech(raw: str, spoken: str) -> None:
    issues = find_issues(raw, spoken)
    if issues:
        detail = "; ".join(f"{item.code} at {item.start} ({item.snippet!r})"
                           for item in issues[:5])
        raise PronunciationPreflightError(f"Scientific TTS preflight blocked: {detail}")


def audit_slide_items(
    slides: list[dict], normalize: Callable[[str], str],
) -> list[dict]:
    """Perform a read-only, offline audit of the entire narration sidecar."""
    findings = []
    for position, item in enumerate(slides, 1):
        raw = str(item.get("tts_text") or item.get("narration") or "")
        spoken = normalize(raw)
        for issue in find_issues(raw, spoken):
            findings.append({"slide": item.get("slide", position),
                             **asdict(issue)})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline TTS pronunciation preflight")
    parser.add_argument("sidecar", type=Path, help="script_tts.json")
    args = parser.parse_args()
    from text_to_speech_v25 import normalize_scientific_speech
    payload = json.loads(args.sidecar.read_text(encoding="utf-8"))
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        parser.error("Expected nonempty slides in narration JSON")
    issues = audit_slide_items(slides, normalize_scientific_speech)
    print(json.dumps({"slides_checked": len(slides), "blocking_issues": issues},
                     indent=2, ensure_ascii=False))
    return 2 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
