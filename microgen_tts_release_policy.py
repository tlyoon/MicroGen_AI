"""MicroGen TTS autonomous technical-release contract, 2026-10-20.

Manual reviews are never prerequisites in the autonomous policy. Actual
technical defects and missing machine evidence must still fail closed.
Do not confuse automated clearance with human certification or full
phonetic/academic/figure/element-highlighting proof.
"""
from __future__ import annotations

AUTONOMOUS = "autonomous"
HUMAN_CERTIFIED = "human-certified"
MODES = frozenset((AUTONOMOUS, HUMAN_CERTIFIED))

TECHNICAL_GATES = (
    "pronunciation_text_preflight",
    "reviewed_lexicon",
    "voice_bound_wav_provenance",
    "wav_pcm_integrity",
    "independent_acoustic_screen",
    "video_duration_and_av_integrity",
)
HUMAN_APPROVALS = (
    "all_slide_listening_approved",
    "academic_review_approved",
    "figures_review_approved",
    "element_level_highlights_approved",
)
UNPROVEN_BY_TECHNICAL_GATES = (
    "all_spoken_phonemes_correct",
    "mathematical_and_pedagogical_soundness",
    "textbook_figure_completeness_and_legibility",
    "element_level_visual_highlight_synchronization",
)

class QAPolicyError(ValueError):
    """An unrecognized or incomplete release decision must not pass."""


def decide_release(checks: dict, policy: str = AUTONOMOUS) -> dict:
    """Separate mandatory technical evidence from optional human attestations.

    The result is a *candidate* readiness decision. No publication,
    overwriting, accreditation, reviewer signing or promotion happens here.
    """
    if policy not in MODES:
        raise QAPolicyError("Unknown TTS QA policy")
    if not isinstance(checks, dict):
        raise QAPolicyError("QA checks must be a mapping")
    expected = TECHNICAL_GATES + HUMAN_APPROVALS
    if any(key not in checks or type(checks[key]) is not bool for key in expected):
        raise QAPolicyError("Missing or non-boolean check; refusing QA decision")
    technical_blockers = [name for name in TECHNICAL_GATES if not checks[name]]
    unreviewed = [name for name in HUMAN_APPROVALS if not checks[name]]
    manual_is_gate = policy == HUMAN_CERTIFIED
    blockers = technical_blockers + (unreviewed if manual_is_gate else [])
    technical_ready = not technical_blockers
    manually_certified = not unreviewed
    return {
        "policy": policy,
        "manual_approval_is_gate": manual_is_gate,
        "technical_blockers": technical_blockers,
        "human_reviews_pending": unreviewed,
        "blockers": blockers,
        "automated_technical_qa_passed": technical_ready,
        "human_qa_certified": manually_certified,
        "ready_for_separate_promotion": not blockers,
        "release_evidence_class": (
            "HUMAN_CERTIFIED_AND_AUTOMATED_QA"
            if manually_certified and technical_ready else
            "AUTOMATED_TECHNICAL_QA_ONLY"
            if technical_ready else "NOT_READY"
        ),
        "unproven_quality_dimensions": list(UNPROVEN_BY_TECHNICAL_GATES),
        "publication_performed": False,
        "no_claim_of_human_review": not manually_certified,
        "explanation": (
            "Autonomous policy does not require manual sign-offs. Verified "
            "technical defects or absent technical evidence still block. "
            "All academic, pronunciation and visual quality claims remain "
            "limited to checks actually performed; no automatic publication."
        ),
    }
