"""Prevent the owner-mandated autonomous-recovery policy disappearing.

This checks the controlling contract, the autonomous QA addendum and the
README discoverability. It is governance coverage, not proof that a real
Gemini failure has recovered or that G2 media acceptance has passed.
"""
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
CONTROLLING = PROJECT / "docs" / "RELEASE_CLOSURE_DEVELOPMENT_CONTRACT_20261107.md"
QA = PROJECT / "docs" / "AUTONOMOUS_QA_DEVELOPMENT_CONTRACT_20261020.md"
README = PROJECT / "README.md"

PRINCIPLE = (
    "automatic recovery must be part of normal pipeline execution, not depend "
    "on the owner repeatedly asking the developer to fix the next blocker."
)


def normalized(path: Path) -> str:
    text = path.read_text(encoding="utf8").casefold()
    # Markdown blockquote continuation markers must not alter the principle.
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    return " ".join(text.split())


def test_binding_principle_is_discoverable_across_all_contract_entrypoints():
    for path in (CONTROLLING, QA, README):
        assert PRINCIPLE in normalized(path), str(path)
    assert "**version:** 1.2" in normalized(CONTROLLING)
    assert "controlling development contract (v1.2" in normalized(README)


def test_controlling_contract_requires_full_automatic_recovery_cycle():
    contract = normalized(CONTROLLING)
    assert "### mandatory automatic recovery and forward progression" in contract
    required = (
        "identify and classify the failure automatically",
        "reuse verified historical remedies automatically",
        "revalidate after each repair",
        "automatically continue downstream",
        "preserve all unaffected verified work",
        "generalize any newly discovered remedy",
        "prevent repeated failure loops",
        "ordinary production entrypoint",
        "historical-failure replay tests",
        "sha-bound",
        "remaining unresolved gate",
    )
    for text in required:
        assert text in contract, text


def test_contract_does_not_convert_an_automated_fix_into_a_qa_or_budget_waiver():
    contract = normalized(CONTROLLING)
    requirements = (
        "both independent gemini",
        "less than 600 seconds",
        "new paid campaign",
        "contradictory independent",
        "fail-closed",
        "no one-off per-slide workaround",
        "do not treat a hold as successful completion",
    )
    for text in requirements:
        assert text in contract, text


def test_contract_requires_future_qa_evidence_not_just_standalone_fixes():
    qa = normalized(QA)
    readme = normalized(README)
    assert "historical failure replay and actual forward stage progression" in qa
    assert "does not waive independent qa" in qa
    assert "automatically continue to downstream stages" in readme
    assert "existing finite authorized scope" in readme
