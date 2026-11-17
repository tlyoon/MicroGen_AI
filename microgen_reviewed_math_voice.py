"""Deterministic reviewed spoken math-variable forms before paid G2 TTS.

Never replace single letters globally: original textbook mathematics, slides,
narration and source PDF remain unchanged. Only narrowly recognized physics
notation can be rendered as an unambiguous *spoken* letter-name token.
Source-side acoustic risks still need two-model evidence on actual WAV.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path


def voice_adapter_code_sha256() -> str:
    """Bind narrator source, speech normalizer and voice policy to sidecar.

    Every ordinary code change to this adapter invalidates old six-stage
    source-bound reuse automatically; no manual policy version bump needed.
    """
    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in ("gen_script_v13.py", "text_to_speech_v25.py",
                 "microgen_reviewed_math_voice.py",
                 "microgen_source_bound_voice_recovery.py"):
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise VoiceRiskPreflightError("Voice-adapter source unavailable")
        h.update(name.encode("utf8") + b"\\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


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

    # Source-form kinematics indices appear in narrated math as a-sub-x,
    # v-sub-x-final, x-initial, x f, and a x t. These are variable
    # roles, not ordinary English letters. Only these explicit structured
    # forms are rewritten, and only for speech; visible mathematics and
    # the original narration are never altered.
    hyphen = r"[-\u2010-\u2015]"
    component_form = re.compile(
        rf"(?<![A-Za-z])(?P<component>[av]){hyphen}sub{hyphen}"
        rf"(?P<axis>[xy])(?P<index>{hyphen}(?:initial|final|average|avg))?\b",
        flags=re.IGNORECASE,
    )
    def speak_component(m):
        index = m["index"]
        suffix = (" " + index[1:].lower()) if index else ""
        return (_COMPONENT[m["component"].lower()] + " sub "
                + _NAMES[m["axis"].lower()] + suffix)
    value = component_form.sub(speak_component, value)

    value = re.sub(
        rf"(?<![A-Za-z])(?P<axis>[xy]){hyphen}(?P<index>initial|final)\b",
        lambda m: _NAMES[m["axis"].lower()] + " " + m["index"].lower(),
        value, flags=re.IGNORECASE,
    )
    # Bare i/f can only be expanded when the immediately following token
    # is an equation operator or punctuation, rather than arbitrary prose.
    value = re.sub(
        r"(?<![A-Za-z])(?P<axis>[xy])\s+(?P<index>[if])\b"
        r"(?=\s*(?:equals?|plus|minus|times|[,.:;!?]|$))",
        lambda m: _NAMES[m["axis"].lower()] +
        (" initial" if m["index"].lower() == "i" else " final"),
        value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<![A-Za-z])(?P<component>[av])\s+(?P<axis>[xy])"
        r"\s+(?P<average>average|avg)\b",
        lambda m: _COMPONENT[m["component"].lower()] + " sub "
        + _NAMES[m["axis"].lower()] + " average",
        value, flags=re.IGNORECASE,
    )
    # Compact equation factors: a_x*t, v_x*t, a_x*(x_f-x_i).
    # Requiring a following mathematical operand prevents global 'a x'
    # or single-letter English rewrites.
    value = re.sub(
        r"(?<![A-Za-z])(?P<component>[av])\s+(?P<axis>[xy])"
        r"\s+(?P<operand>t|times)\b",
        lambda m: _COMPONENT[m["component"].lower()] + " sub "
        + _NAMES[m["axis"].lower()]
        + (" times tee" if m["operand"].lower() == "t" else " times"),
        value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<![A-Za-z])(?P<component>[av])\s+(?P<axis>[xy])"
        r"(?=\s+[xy]\s+(?:[if]|initial|final)\b)",
        lambda m: _COMPONENT[m["component"].lower()] + " sub "
        + _NAMES[m["axis"].lower()] + " times",
        value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\bd\s+v\s+(?P<axis>[xy])\s+d\s+t\b",
        lambda m: "dee vee sub " + _NAMES[m["axis"].lower()]
        + " over dee tee", value, flags=re.IGNORECASE,
    )

    # Equation operators also attest that bare x i / x f are compact
    # initial/final position indices, even when an English verb follows.
    value = re.sub(
        r"(?P<operator>\b(?:times|minus|plus|equals?|by)\s+)"
        r"(?P<axis>[xy])\s+(?P<index>[if])\b",
        lambda m: m["operator"] + _NAMES[m["axis"].lower()]
        + (" initial" if m["index"].lower() == "i" else " final"),
        value, flags=re.IGNORECASE,
    )
    # General physics displacement/time increments: the spoken source
    # variables in "delta x", "delta y" and "delta t" are letter names,
    # not English words. Correct only this explicit math-prefix context.
    delta_names = {"x": "ex", "y": "why", "t": "tee"}
    value = re.sub(
        r"\bdelta\s+(?P<axis>[xyt])\b",
        lambda m: "delta " + delta_names[m["axis"].lower()],
        value, flags=re.IGNORECASE,
    )
    # Figure panels are not mathematical coefficients. Gemini may express
    # an authentic printed reference Figure 2.10c as "Figure 2 point 10 c".
    # Preserve exactly the numbered figure identity and speak the separate
    # panel label explicitly; never rewrite an unrelated solitary c/C.
    panel_names = {
        "a": "ay", "b": "bee", "c": "see",
        "d": "dee", "e": "ee", "f": "eff",
    }
    value = re.sub(
        r"\b(?P<figure>(?:figure|fig\.?)\s+\d+\s*(?:point|\.)\s*\d+)"
        r"\s*(?P<panel>[a-f])\b",
        lambda m: m["figure"] + " panel " +
                  panel_names[m["panel"].lower()],
        value, flags=re.IGNORECASE,
    )

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

    # Explicit positional subscripts in the spoken scientific equation are
    # variable names, never the unrelated English x or a random standalone
    # letter. Convert only the formula role: "x sub i / f", "x sub B",
    # "x car / x trooper", and "v x car / v x i / v x f".
    # Preserve symbols, labels and equation values in source/narration.
    subscript_letter_names = {
        "i": "eye", "f": "eff", "b": "bee",
        "car": "car", "trooper": "trooper",
    }
    value = re.sub(
        r"(?<![A-Za-z])(?P<axis>x|y)\s+sub\s+"
        r"(?P<index>i|f|B|car|trooper)\b",
        lambda m: _NAMES[m["axis"].lower()] + " sub " +
                  subscript_letter_names[m["index"].lower()],
        value,
    )
    value = re.sub(
        r"(?<![A-Za-z])v\s+x\s+(?P<index>i|f|B|car|trooper)\b",
        lambda m: "vee ex " + subscript_letter_names[m["index"].lower()],
        value,
    )
    value = re.sub(
        r"(?<![A-Za-z])x\s+(?P<index>B|car|trooper)\b"
        r"(?=\s*(?:equals?|plus|minus|times|to|aligns|[,.:;!?]|$))",
        lambda m: "ex " + subscript_letter_names[m["index"].lower()],
        value,
    )

    # Graph panel labels printed a-f are letters ("Graph c" is NOT the
    # coefficient c, nor 'circa'). Only in explicitly graphical references
    # or a labelled a,b,c graph sequence do we read panel names aloud.
    value = re.sub(
        r"\b(?P<graph>graphs?)\s+(?P<letter>[a-f])\b",
        lambda m: m["graph"] + " panel " +
                  panel_names[m["letter"].lower()],
        value, flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(?P<stem>(?:graphs?\s+)?labeled\s+)a\s*,\s*b\s*,\s*"
        r"(?:and\s+)?c\b",
        lambda m: m["stem"] + "panel ay, panel bee, and panel see",
        value, flags=re.IGNORECASE,
    )
    # For "graphs a, b, and c" all labels refer to the same printed
    # multi-panel source figure. Accept both the raw list and the form
    # already handled by the singular graph-label expression above.
    value = re.sub(
        r"\bgraphs\s+(?:panel\s+ay|a)\s*,\s*b\s*,\s*(?:and\s+)?c\b",
        "graphs panel ay, panel bee, and panel see",
        value, flags=re.IGNORECASE,
    )

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

    # Reuse the historical source-bound spoken x-component clarifier only
    # for complete equation roles implicated by independent ASR recurrences.
    # Do NOT revoice a previously grounded standalone summary or average
    # velocity identity: unnecessary paraphrases can exhaust the fixed
    # four-slide semantic cue budget before the genuine risk is reached.
    # This is a structural equation-role filter, NOT a slide/page number
    # exception, nor a waiver for reviewers hearing a mathematical y-axis.
    risk_equation_patterns=(
        r"\bay\s+sub\s+ex\s+equals\s+vee\s+sub\s+ex\b",
        r"\bay\s+sub\s+ex\s+times\s+(?:t|tee)\b",
        r"\bvee\s+sub\s+ex\s+final\s+equals\s+vee\s+sub\s+ex\s+initial\s+plus\b",
        r"\bv\s+ex\s+final\s+equals\s+v\s+ex\s+initial\s+plus\b",
        r"\bay\s+ex\s+equals\s+the\s+fraction\b",
        r"\bconstant\s+speed\s+vee\s+ex\s+car\s+of\b",
        r"\bone-half\s+of\s+v\s+ex\s+initial\s+plus\s+v\s+ex\s+final\b",
    )
    if any(re.search(pattern,value,flags=re.I)
           for pattern in risk_equation_patterns):
        from microgen_source_bound_voice_recovery import clarify_x_component
        value=re.sub(
            r"\bv\s+ex(?=\s+(?:initial|final|eye|eff|car|trooper)\b)",
            "vee ex",value,flags=re.I)
        value=clarify_x_component(value)

    # Recurrent two-Gemini x/y confusion in compact a_x speech is a
    # pronunciation hazard, not harmless orthographic ASR variation.
    # Expand ONLY an independently source-identifiable acceleration label
    # or full equation-introduction role. Avoid global a_x substitution:
    # previous full-lecture cue preflight proved that broad paraphrases
    # exceed the fixed semantic mapping budget on unrelated slides.
    from microgen_source_bound_voice_recovery import clarify_x_component
    value=re.sub(
        r"\b(?P<relation>slope\s+(?:equals|equal\s+to)\s+the\s+)"
        r"(?P<component>acceleration\s+ay\s+(?:sub\s+)?ex)\b"
        r"(?!\s+(?:average|avg)\b)",
        lambda m:m["relation"]+clarify_x_component(m["component"]),
        value,flags=re.I)
    value=re.sub(
        r"\b(?P<intro>defined\s+as|means|when)\s+"
        r"(?P<variable>ay\s+(?:sub\s+)?ex)\s+equals\b",
        lambda m: m["intro"]+" "+clarify_x_component(m["variable"])+" equals",
        value,flags=re.I)
    value=re.sub(
        r"\b(?P<lhs>the\s+x\s+component\s+of\s+acceleration\s+equals)\s+"
        r"(?P<rhs>ay\s+(?:sub\s+)?ex\s+(?:average|avg))\b",
        lambda m:m["lhs"]+" "+clarify_x_component(m["rhs"]),
        value,flags=re.I)

    # A source-bound fraction (0 - initial speed)/duration needs the
    # subtraction grouped aloud. Do not convert a two-digit integer to a
    # decimal or assume 63 ~= 6.3: name the WHOLE numerical value and the
    # numerator while retaining all original digits, sign and denominator.
    value=re.sub(
        r"\bgives\s+(?P<zero>0)\s+minus\s+(?P<whole>[1-9]\d{1,2})"
        r"\s+divided\s+by\s+(?P<duration>(?!0+(?:\.0+)?\b)\d+(?:\.\d+)?)\b",
        lambda m: ("gives the numerator "+m["zero"]+
                   " minus the whole-number value "+m["whole"]+
                   " with that entire numerator divided by "+m["duration"]),
        value, flags=re.I)

    # Explicit spoken multiplication, not an omitted word, prevents
    # equation-term boundaries from silently disappearing in independent
    # recognizers. Only numerically exact speed x time and half x factor
    # constructions qualify, preserving every source quantity.
    value=re.sub(r"\bone-half\s+times\b",
                 "one-half multiplied by",value,flags=re.I)
    value=re.sub(
        r"\b(?P<speed>\d+(?:\.\d+)?\s+meters\s+per\s+second)"
        r"\s+times\s+(?P<duration>\d+(?:\.\d+)?\s+seconds)\b",
        lambda m:m["speed"]+", multiplied by "+m["duration"],
        value,flags=re.I)

    # The ungrouped spoken factor "a_x times x_final minus x_initial"
    # is ambiguous even when the PRINTED source is a_x*(x_f-x_i).
    # Independent blind acoustic reviewers once both inserted a spurious
    # "plus x final" at this exact factor boundary. Preserve every source
    # index/sign/value and add ONLY the spoken grouping word. The normal
    # source/figure/math timed-cue admission must still independently pass
    # before any new TTS billable operation, and fresh ASR is mandatory.
    value=re.sub(
        r"\b(?P<factor>(?:the\s+)?(?:x|ex)\s+component\s+of\s+"
        r"acceleration\s+times)\s+"
        r"(?P<difference>(?:x|ex)\s+final\s+minus\s+(?:x|ex)\s+initial)\b",
        lambda m: m["factor"]+" the quantity "+m["difference"],
        value,flags=re.I)

    # Two independent audio transcriptions disagreed about the two MINUS
    # operators in the quadratic a_x*t^2/2 - v_x*t - x_B = 0. Describe
    # the complete factor and BOTH subtractions aloud; do not change the
    # coefficient, exponent, variable index or equality. This is a
    # deterministic wording proposal, never a post-hoc acoustic waiver.
    value=re.sub(
        r"\b(?P<lead>one-half\s+the\s+x\s+component\s+of\s+acceleration)"
        r"\s+times\s+tee\s+squared\s+minus\s+"
        r"(?P<velocity>the\s+car's\s+x\s+component\s+of\s+velocity)"
        r"\s+times\s+(?:t|tee)\s+minus\s+"
        r"(?P<position>ex\s+bee)\s+equals\s+0\b",
        lambda m:(m["lead"]+" multiplied by tee squared, minus the full "
                  "product of "+m["velocity"]+" multiplied by tee, and "
                  "minus the position term "+m["position"]+" equals 0"),
        value, flags=re.I)

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
        "voice_adapter_code_sha256": voice_adapter_code_sha256(),
        "changed_for_tts_only": corrected != text,
        "unresolved_source_risk_codes": sorted({r.code for r in residual}),
        "unresolved_source_risk_count": len(residual),
        "phoneme_certified": False,
        "publication_allowed": False,
    }


class VoiceRiskPreflightError(RuntimeError):
    """Predictable unresolved pronunciation risk; do not spend on new TTS."""


def preflight_voice_sidecar(stage, *, require_policy_binding: bool = False) -> dict:
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
        if proof is None and require_policy_binding:
            raise VoiceRiskPreflightError(
                "STALE_VOICE_ADAPTER_SOURCE_HOLD: missing source-code-"
                "bound voice sidecar; regenerate narration before paid TTS")
        if proof is not None:
            if (not isinstance(proof, dict)
                    or proof.get("voice_adapter_code_sha256") !=
                    voice_adapter_code_sha256()):
                raise VoiceRiskPreflightError(
                    "STALE_VOICE_ADAPTER_SOURCE_HOLD: the narration adapter "
                    "code changed; rebuild voice sidecar and independent "
                    "science QA before any paid TTS")
            if (proof.get("schema_version") != 1
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
