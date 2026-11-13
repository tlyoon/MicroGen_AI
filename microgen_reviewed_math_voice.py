"""Deterministic reviewed spoken math-variable forms before paid G2 TTS.

Never replace single letters globally: original textbook mathematics, slides,
narration and source PDF remain unchanged. Only narrowly recognized physics
notation can be rendered as an unambiguous *spoken* letter-name token.
Source-side acoustic risks still need two-model evidence on actual WAV.
"""
from __future__ import annotations
import hashlib
import re

_NAMES = {"x": "ex", "y": "why", "c": "see"}
_COMPONENT = {"a": "ay", "v": "vee", "d": "dee"}


def reviewed_math_voice(text: str) -> str:
    """Expand only explicitly mathematical variable syntax in TTS text.

    This is **not** pronunciation certification; it prevents easily
    avoidable ambiguous speech input while preserving the raw narration.
    """
    if not isinstance(text, str):
        raise TypeError("TTS voice input must be text")
    value = text

    # Printed a_x, v_x and d x/d t frequently arrive as "a x", "v x",
    # "d x over d t" in model-generated narration. Do not rewrite an
    # isolated English x, product name or arbitrary single-character word.
    value = re.sub(
        r"(?<![A-Za-z])(?P<var>[avd])\s+(?P<axis>[xy])\b"
        r"(?=\s*(?:[,.:;!?]|$|(?:avg|over|versus|equals?|is|at|of|and|as|becomes|both)\b))",
        lambda m: _COMPONENT[m["var"].lower()] + " " +
                  _NAMES[m["axis"].lower()],
        value,
    )
    # Second-derivative numerator d squared x is explicitly symbolic.
    value = re.sub(r"\bd\s+squared\s+x\b", "dee squared ex", value)
    # Unambiguous narrated symbolic subscripts; no assumption about
    # multi-letter variables, element labels or index arithmetic.
    value = re.sub(
        r"\bsub\s+(?P<axis>[xy])\b",
        lambda m: "sub " + _NAMES[m["axis"].lower()],
        value,
        flags=re.IGNORECASE,
    )
    # Once a subscript has been named explicitly, its one-letter
    # component coefficient is also a spoken mathematical letter.
    value = re.sub(
        r"(?<![A-Za-z])(?P<var>[avd])\s+sub\s+(?P<axis>ex|why)\b",
        lambda m: _COMPONENT[m["var"].lower()] + " sub " + m["axis"],
        value,
    )
    # Distinguish a symbolic point label C from "circa" only after
    # an explicit time-variable cue; leave historical abbreviations alone.
    value = re.sub(
        r"\btime\s+t\s+C\b(?=\s*(?:[,.;!?]|$|where\b))",
        "time tee see", value,
    )
    # Explicitly named component derivative and plot notation.
    value = re.sub(
        r"\b(?P<axis>ex|why|x|y)\s+versus\s+t\b",
        lambda m: (_NAMES.get(m["axis"].lower(), m["axis"].lower()))
        + " versus tee", value, flags=re.IGNORECASE)
    # Physically readable coefficient c times t, not a general c/C match.
    value = re.sub(r"\bminus\s+c\s+t\b", "minus see tee", value)

    # Authentic G2 independent TWO-MODEL acoustic failures demonstrated that
    # compact variable names adjacent to ordinary grammar can sound like a
    # different equation ("ay ex as" -> "ay equals"). Prefer the same
    # scholarly meaning as an explicit x-component statement. This modifies
    # ONLY the voice input, never visible narration or textbook mathematics.
    value = re.sub(
        r"\binstantaneous\s+acceleration\s*,?\s+ay\s+ex\s*,?\s+"
        r"as\s+the\s+limit\b",
        "instantaneous acceleration along the ex axis as the limit",
        value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\brepresents\s+average\s+acceleration\s*,?\s+"
        r"ay\s+ex\s*,?\s+avg\b",
        "represents average acceleration along the ex axis",
        value, flags=re.IGNORECASE,
    )
    # Both blind recognizers inserted an unsupported squared term when a
    # terse polynomial was read aloud. Make multiplication and the cubic
    # exponent separately audible. Never change the sign or exponent.
    value = re.sub(
        r"\bposition\s+(?:ex|x)\s+of\s+(?:tee|t)\s+equals\s+"
        r"b\s+(?:tee|t)\s+cubed\s+minus\s+(?:see\s+tee|c\s+t)\b",
        "position ex at time tee equals "
        "b multiplied by tee cubed minus see multiplied by tee",
        value, flags=re.IGNORECASE,
    )
    # Historical 13-Nov 2026 source-bound G2 two-model recognition followed
    # by a blind third reviewer could not corroborate whether a velocity
    # equation said "forty" or "four t". The original source equation was
    # v_x = 40 - 5t^2; neither a numerical mismatch nor a changed exponent
    # may be waived in acoustic QA. Phrase *the constant term* explicitly
    # in the spoken mathematics BEFORE paid TTS, and separate the subtraction
    # instruction. This is a reusable pattern for quadratic kinematics,
    # not a slide/page-specific patch, and leaves visible narration intact.
    tens={20:"twenty",30:"thirty",40:"forty",50:"fifty",
          60:"sixty",70:"seventy",80:"eighty",90:"ninety"}
    small={"1":"one","2":"two","3":"three","4":"four","5":"five",
           "6":"six","7":"seven","8":"eight","9":"nine","10":"ten"}
    formula=re.compile(
        r"\b(?P<quantity>velocity\s+vee\s+ex|position\s+ex|"
        r"acceleration\s+ay\s+ex)\s+equals\s+"
        r"(?P<const>[2-9]0)\s+minus\s+"
        r"(?P<coef>[1-9])\s+(?:tee|t)\s+squared\b",
        flags=re.IGNORECASE,
    )
    def clarify_constant_equation(match):
        value_number=int(match["const"])
        coefficient=match["coef"]
        # A full sentence break and "fixed numerical value" distinguish
        # the tens constant from an adjacent letter-name such as 4 t.
        # The same exact numeric source evidence is still required.
        return (f"{match['quantity']} equals the constant term "
                f"{tens[value_number]}, a fixed numerical value. "
                "Then subtract "
                f"{small.get(coefficient,coefficient)} multiplied by "
                "the square of time")
    value=formula.sub(clarify_constant_equation,value)

    return value


def voice_input_risk_status(text: str, normalize) -> dict:
    """Hash-only predictable source risk status; never log raw narration."""
    from microgen_tts_risk_register import find_pronunciation_risks
    corrected = normalize(reviewed_math_voice(text))
    residual = find_pronunciation_risks(corrected, corrected)
    return {
        "schema_version": 1,
        "text_before_sha256": hashlib.sha256(text.encode("utf8")).hexdigest(),
        "voice_input_sha256": hashlib.sha256(corrected.encode("utf8")).hexdigest(),
        "changed_for_tts_only": corrected != text,
        "unresolved_source_risk_codes": sorted({r.code for r in residual}),
        "unresolved_source_risk_count": len(residual),
        "phoneme_certified": False,
        "publication_allowed": False,
    }


class VoiceRiskPreflightError(RuntimeError):
    """Predictable unresolved pronunciation risk; do not spend on new TTS."""


def preflight_voice_sidecar(stage) -> dict:
    """Source/WAV-independent G2 preflight before the FIRST paid TTS send.

    The acoustic screen already marks unnormalized mathematical letters as
    mandatory review. Prevent known doomed generations before billing, while
    retaining the independent audio/visual acceptance gates for safe text.
    """
    import json
    from pathlib import Path
    from text_to_speech_v25 import normalize_scientific_speech
    from microgen_tts_risk_register import find_pronunciation_risks

    stage = Path(stage)
    path = stage / "script_tts.json"
    if path.is_symlink() or not path.is_file():
        raise VoiceRiskPreflightError("Voice sidecar missing or linked")
    try:
        document = json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise VoiceRiskPreflightError("Invalid voice sidecar JSON") from exc
    slides = document.get("slides") if isinstance(document, dict) else None
    if (not isinstance(slides, list) or not slides
            or [r.get("slide") if isinstance(r, dict) else None for r in slides]
            != list(range(1, len(slides)+1))):
        raise VoiceRiskPreflightError("Unordered voice source or empty slides")
    blocked = []
    for row in slides:
        spoken = row.get("tts_text") or row.get("narration")
        if not isinstance(spoken, str) or not spoken.strip():
            raise VoiceRiskPreflightError("Empty spoken lecture source")
        actual_input = normalize_scientific_speech(spoken)
        current_reviewed = normalize_scientific_speech(
            reviewed_math_voice(spoken))
        if current_reviewed != actual_input:
            # An old, individually safe narration may use a voice spelling
            # superseded by a more source-faithful acoustic remedy. The
            # six-stage prior-campaign import must not treat that old voice
            # sidecar (or its science receipt) as current-code acceptance.
            # The importer retains the four independently verified source/
            # slide stages and rebuilds narration from verified model caches.
            raise VoiceRiskPreflightError(
                "STALE_VOICE_ADAPTER_SOURCE_HOLD: current acoustic math "
                "voice policy changes a prior sidecar; regenerate the "
                "voice-only narration and independent science QA, do not "
                "replay or approve old PCM")
        risk_list = find_pronunciation_risks(spoken, actual_input)
        if risk_list:
            blocked.append((row["slide"], len(risk_list)))
        # Hash-bound proof generated by the new narrator, when present:
        proof = row.get("tts_math_voice_preflight")
        if proof is not None:
            if (not isinstance(proof, dict) or proof.get("schema_version") != 1
                    or proof.get("unresolved_source_risk_count") != 0
                    or proof.get("voice_input_sha256") !=
                    hashlib.sha256(actual_input.encode("utf8")).hexdigest()
                    or proof.get("phoneme_certified") is not False
                    or proof.get("publication_allowed") is not False):
                raise VoiceRiskPreflightError(
                    "Reviewed voice-preflight receipt mismatch or drift")
    if blocked:
        names = ",".join(str(n) for n, _ in blocked[:25])
        raise VoiceRiskPreflightError(
            "PREDICTABLE_MATH_VOICE_RISK_PREPAY_HOLD: unresolved "
            f"source notation on {len(blocked)} slide(s) [{names}]; "
            "repair reviewed spoken input during narration before paid TTS; "
            "never waive independent acoustic QA")
    return {
        "status": "VOICE_SOURCE_RISK_OFFLINE_PREFLIGHT_PASSED",
        "slide_count": len(slides),
        "source_risk_count": 0,
        "script_tts_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "acoustic_qa_required": True,
        "publication_allowed": False,
    }
