"""Conservative, independent acoustic TTS QA for MicroGen_AI.

Independent recognition is a diagnostic signal, not phonetic proof.
The autonomous technical QA contract does not require manual approval;
unresolved technical mismatches and missing evidence remain blockers.
This tool never publishes teaching outputs or signs human review.

No Whisper or ASR library installation is required. Gemini recognition is
opt-in, credentials are read from the user's established Microvid config.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

RECEIPT = ".microgen_tts_acoustic_qa.json"
# Always require another review when mathematical content is at stake.
SENSITIVE = set("""
circa limit limits theorem intermediate value derivative derivatives
continuous continuity discontinuity integral integrals minus plus
positive negative numerator denominator fraction infinite infinity
equals equal point zero one two three four five six seven eight nine ten
not never no greater less negative positive above below minus multiplied divided
subtract subtracted subtracting add added adding multiply multiplying divide dividing
squared cubed
""".split()) | set("0 1 2 3 4 5 6 7 8 9 10".split())

class AcousticQAError(RuntimeError):
    """Missing/unreliable independent verification: fail closed."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tokens(text: str) -> list[str]:
    """Canonicalize only equivalent spoken forms; preserve math/negation changes.

    Punctuation, hyphenated words, expanded contractions, and spellings of
    numbered equation references must not inflate the acoustic error budget.
    A removed mathematical sign, changed digit or changed subscript letter
    remains a real discrepancy.
    """
    # Recycle exact mathematical notation equivalences previously observed
    # in independent Gemini ASR (vee ex / v_x, t=0 / t equals zero).
    # This is script-blind and never drops signs or numerical exponents.
    from microgen_acoustic_math_transcript import canonical_math_transcript
    text = canonical_math_transcript(text)
    # The hyphen between non and isolated does not change the audible word.
    text = re.sub(r"\bnon[\s-]?isolated\b", "non isolated", text,
                  flags=re.IGNORECASE)
    # Some ASR models choose the contraction even when the TTS script did not.
    text = re.sub(r"\b(you|we|they|i)['\u2019]ve\b",
                  lambda m: m.group(1) + " have", text,
                  flags=re.IGNORECASE)
    numbers = {"zero": "0", "one": "1", "two": "2", "three": "3",
               "four": "4", "five": "5", "six": "6", "seven": "7",
               "eight": "8", "nine": "9", "ten": "10",
               # Independent ASR may transcribe the SAME audible exact
               # mathematical value as a spelled word or digit. Preserve
               # numerically different values (40 != 50, 40 != 4 t).
               "twenty": "20", "thirty": "30", "forty": "40",
               "fifty": "50", "sixty": "60", "seventy": "70",
               "eighty": "80", "ninety": "90"}
    digits = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    # "Equation eight point two" and "Equation 8.2" are the same citation.
    # Do not discard "point" from general decimal measurements.
    reference = re.compile(
        rf"\b(equation|figure|section|chapter|table|example|exercise|quiz)"
        rf"\s+({digits})\s+point\s+({digits})\b", re.IGNORECASE)
    text = reference.sub(lambda m: (
        f"{m.group(1)} {numbers.get(m.group(2).lower(), m.group(2))}."
        f"{numbers.get(m.group(3).lower(), m.group(3))}"), text)
    # A spoken coordinate x(t) or y(t) can be written by independent ASR
    # as "x of t" even when TTS was explicitly fed "ex of tee".
    # Canonicalize only this complete variable-of-time phrase: never
    # equate arbitrary t/tee words, or suppress genuine "yay"/"circa" flags.
    text = re.sub(
        r"\b(?P<coordinate>ex|x|why|y)\s+of\s+(?:t|tee)\b",
        lambda m: ("ex" if m["coordinate"].lower() in {"x", "ex"}
                   else "why") + " of tee",
        text, flags=re.IGNORECASE,
    )
    # A decimal separator is a meaningful spoken mathematical token.
    # Never conflate 8.2 with the two separate values 8 and 2.
    text = re.sub(r"(?<=\d)\.(?=\d)", " point ", text)
    raw = re.findall(r"[A-Za-z]+|\d+", text.lower())
    out = []
    for i, w in enumerate(raw):
        w = {"c": "see", "sea": "see", "x": "ex", "why": "y",
             "twos": "two"}.get(w, w)
        w = numbers.get(w, w)
        # Script "T sub M T" may be recognized as "T sub MT". Split
        # compact two-letter indices only in an explicit subscript phrase.
        if (i >= 2 and raw[i-1] == "sub" and len(raw[i-2]) == 1
                and len(w) == 2 and w.isalpha()
                and w not in {"is", "be", "to", "of", "on", "in",
                              "at", "an", "or", "it", "as", "by",
                              "we", "he", "no", "do"}):
            out.extend(w)
        else:
            out.append(w)
    return out


def mismatch_details(expected: str, heard: str) -> dict:
    e = tokens(expected)
    h = tokens(heard)
    if not e or not h:
        raise AcousticQAError("Empty expected or independently recognized speech")
    matcher = SequenceMatcher(None, e, h, autojunk=False)
    issues = []
    changed = 0
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed += max(b-a,d-c)
        missing = e[a:b]
        extra = h[c:d]
        edits=set(missing) | set(extra)
        unit_words=set(
            "meter meters metre metres kilometer kilometers kilometre "
            "kilometres centimeter centimeters millimeter millimeters "
            "second seconds minute minutes hour hours newton newtons "
            "joule joules watt watts hertz volts voltage m km cm mm s".split())
        unit_aliases={
            ("meters","m"),("meter","m"),("metres","m"),("metre","m"),
            ("kilometers","km"),("kilometer","km"),("kilometres","km"),
            ("seconds","s"),("second","s"),("centimeters","cm"),
            ("millimeters","mm"),("minutes","min"),("hours","h"),
        }
        pair=(" ".join(missing)," ".join(extra))
        safe_unit_pair=pair in unit_aliases or (pair[1],pair[0]) in unit_aliases
        significant=bool(
            edits & SENSITIVE
            or any(word.isdecimal() for word in edits)
            or edits & unit_words
            or edits & set(
                "eleven twelve thirteen fourteen fifteen sixteen seventeen "
                "eighteen nineteen twenty thirty forty fifty sixty seventy "
                "eighty ninety hundred thousand million billion".split())
        ) and not safe_unit_pair
        issues.append({
            "kind": tag,
            "expected": " ".join(missing),
            "recognized": " ".join(extra),
            "sensitive": significant,
            "expected_token_start": a,
        })
    wer_proxy = changed / max(1,len(e))
    # Explicit detection of letter-name errors even when the number of
    # mismatched words is below the document-wide discrepancy threshold.
    circa_substitutions = [x for x in issues if "circa" in x["recognized"].split()]
    math_y_to_yay = [x for x in issues
                     if "y" in x["expected"].split()
                     and "yay" in x["recognized"].split()]
    return {
        "expected_tokens": len(e),
        "recognized_tokens": len(h),
        "difference_fraction_upper_bound": round(wer_proxy,5),
        "sensitive_mismatches": sum(x["sensitive"] for x in issues),
        "circa_red_flags": len(circa_substitutions),
        "letter_y_yay_red_flags": len(math_y_to_yay),
        "differences": issues,
    }


# Fixed production ceiling for *minor* model-to-model spelling/wording noise.
# This is a second, tightly scoped pathway; the original strict 5% policy
# still governs all sensitive maths and genuine phonetic discrepancies.
MINOR_ASR_SOURCE_WER=0.09
MINOR_ASR_PAIR_WER=0.15
MINOR_ASR_MIN_SOURCE_WORDS=30
_MINOR_MATH_WORDS=set("""
a b c d t v x y z vee tee see ay ex plus minus divide divided times
multiplied squared cubed derivative acceleration velocity acceleration
equation equals equal positive negative zero one two three four five six
seven eight nine ten meter meters metre metres kilometer kilometers
kilometre kilometres centimeter centimeters millimeter millimeters
second seconds minute minutes hour hours kilometer per squared cubed
newton newtons joule joules watt watts hertz volts voltage
""".split()) | set(str(x) for x in range(10))
_MINOR_NUMBER_WORDS=set("""
eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen
twenty thirty forty fifty sixty seventy eighty ninety hundred thousand
million billion
""".split())
_MINOR_SAFE_ALIASES={
    ("vee","v"), ("tee","t"), ("meters","m"), ("meter","m"),
    ("seconds","s"), ("second","s"),
    ("t a","ta"), ("t b","tb"), ("t see","tc"), ("t c","tc"),
    ("v a","va"), ("v b","vb"),
}


def verified_minor_asr_variation(expected:str, heard_a:str, heard_b:str,
                                 *, max_difference_fraction:float=0.05)->bool:
    """Source-bound, narrow exception for harmless two-reviewer ASR variation.

    Every original comparison remains in the report. The reviewer is never
    given expected words. No numerical/mathematical/negation alteration, long
    omission, unintelligible segment or one-sided phonetic red flag qualifies.
    Fixed budgets intentionally do NOT grow with user supplied tolerance.
    """
    if max_difference_fraction>0.05 or max_difference_fraction<0:
        return False
    if len(tokens(expected))<MINOR_ASR_MIN_SOURCE_WORDS:
        return False
    if any(x in text.lower() for text in (heard_a,heard_b)
           for x in ("[unclear]","[inaudible]")):
        return False
    comparisons=[mismatch_details(expected,heard_a),
                 mismatch_details(expected,heard_b)]
    pair=mismatch_details(heard_a,heard_b)
    if (any(comp["sensitive_mismatches"] or comp["circa_red_flags"]
            or comp["letter_y_yay_red_flags"] for comp in (*comparisons,pair))
            or any(comp["difference_fraction_upper_bound"]>MINOR_ASR_SOURCE_WER
                   for comp in comparisons)
            or pair["difference_fraction_upper_bound"]>MINOR_ASR_PAIR_WER):
        return False
    for comp in comparisons:
        # At most 8 changed tokens and 5 short disjoint edits per reviewer.
        # Avoid accepting missing sentences even on a long slide.
        if len(comp["differences"])>5:
            return False
        changed=0
        for issue in comp["differences"]:
            left=issue["expected"].split()
            right=issue["recognized"].split()
            changed+=max(len(left),len(right))
            if max(len(left),len(right))>2:
                return False
            words=set(left+right)
            alias=(" ".join(left)," ".join(right))
            reverse=(alias[1],alias[0])
            if alias in _MINOR_SAFE_ALIASES or reverse in _MINOR_SAFE_ALIASES:
                continue
            if (words & (_MINOR_MATH_WORDS|_MINOR_NUMBER_WORDS)
                    or any(word.isdecimal() for word in words)):
                return False
            # Non-math wording drift can be tolerated only in one-word edits.
            if max(len(left),len(right))>1:
                return False
        if changed>8:
            return False
    return True


def verified_numeric_fragment_tiebreak(
        expected:str,heard_a:str,heard_b:str,third_heard:str)->bool:
    """Require 2/3 source-BLIND model support for one narrow number/letter split.

    E.g. a model may hear spoken 'forty' as '4 t' while the other spells
    '40'. This is NOT a general numeric-tolerance policy: '40' -> '50',
    sign changes, equations/exponents, omissions and two changed numbers
    all remain blockers even when the third reviewer agrees with source.
    """
    import re
    if len(tokens(expected)) < MINOR_ASR_MIN_SOURCE_WORDS:
        return False
    if any(marker in word.lower() for word in (heard_a,heard_b,third_heard)
           for marker in ("[unclear]","[inaudible]")):
        return False
    originals=[mismatch_details(expected,heard_a),
               mismatch_details(expected,heard_b)]
    good_indexes=[i for i,comp in enumerate(originals)
                  if (comp["difference_fraction_upper_bound"]<=0.05
                      and not (comp["sensitive_mismatches"]
                               or comp["circa_red_flags"]
                               or comp["letter_y_yay_red_flags"]))]
    if len(good_indexes)!=1:
        return False
    bad=originals[1-good_indexes[0]]
    if (bad["difference_fraction_upper_bound"]>MINOR_ASR_SOURCE_WER
            or bad["circa_red_flags"] or bad["letter_y_yay_red_flags"]
            or len(bad["differences"])>5
            or bad["sensitive_mismatches"]!=1):
        return False
    fragments=0
    for issue in bad["differences"]:
        left=issue["expected"].split()
        right=issue["recognized"].split()
        if issue["sensitive"]:
            # ASR number/letter segmentation only, never a changed value.
            if (len(left)!=1 or len(right)!=2
                    or not re.fullmatch(r"[1-9]0",left[0])
                    or right != [left[0][0],"t"]):
                return False
            fragments+=1
        else:
            if ((" ".join(left)," ".join(right)) not in _MINOR_SAFE_ALIASES
                    and (" ".join(right)," ".join(left)) not in _MINOR_SAFE_ALIASES):
                return False
    if fragments!=1:
        return False
    candidate=mismatch_details(expected,third_heard)
    agreeing=mismatch_details((heard_a,heard_b)[good_indexes[0]],third_heard)
    for row in (candidate,agreeing):
        if (row["difference_fraction_upper_bound"]>0.05
                or row["sensitive_mismatches"]
                or row["circa_red_flags"] or row["letter_y_yay_red_flags"]):
            return False
    return True


def _input_snapshot(folder: Path, count: int) -> dict[str,str]:
    """Pin the actual WAVs, sidecar (if present), and voice-bound manifest."""
    names=[".microgen_tts_provenance.json"]+[f"slide{i}.wav" for i in range(1,count+1)]
    if (folder/"script_tts.json").is_file():
        names.append("script_tts.json")
    return {name:sha256(folder/name) for name in names}


def audit_with_recognizer(
    folder: Path, raw_texts: list[str],
    recognizer: Callable[[Path], str], normalize: Callable[[str],str],
    *, independent_recognizer: Callable[[Path], str] | None = None,
    recognition_models: tuple[str,str] = ("offline-primary", "offline-secondary"),
    max_difference_fraction: float = 0.05,
) -> dict:
    """Audio-first two-pass transcript comparison. Does not rewrite audio.

    Any mismatch, model failure, conflicting independent transcripts, or
    dubious math term requires manual inspection and blocks auto acceptance.
    Passing means ONLY 'no issue detected by these recognizers'.
    """
    if not 0 <= max_difference_fraction <= 0.2:
        raise ValueError("Unsafe permissive mismatch threshold")
    if independent_recognizer is None:
        raise ValueError("Second independent recognizer is required for acoustic QA")
    if len(recognition_models) != 2 or not all(recognition_models) or recognition_models[0] == recognition_models[1]:
        raise ValueError("Two distinct audio model identities must be recorded")
    from microgen_tts_provenance import verify_manifest
    from microgen_tts_risk_register import find_pronunciation_risks
    from dataclasses import asdict
    folder = Path(folder)
    expected = [normalize(s) for s in raw_texts]
    verify_manifest(folder, expected)
    input_snapshot=_input_snapshot(folder,len(expected))
    rows = []
    unavailable_engines: set[int] = set()
    for n, text in enumerate(expected,1):
        wav = folder / f"slide{n}.wav"
        attempts = []
        for engine_index, recognition_engine in enumerate((recognizer, independent_recognizer)):
            if engine_index in unavailable_engines:
                attempts.append("")
                continue
            try:
                transcript = str(recognition_engine(wav)).strip()
                if len(transcript) < 5:
                    raise AcousticQAError("Empty/too-short transcript")
                attempts.append(transcript)
            except Exception:
                # Avoid 17 repeated paid retries after a quota/outage;
                # fail closed for the remaining slides in this audit.
                unavailable_engines.add(engine_index)
                attempts.append("")
        findings = []
        if len(attempts) != 2 or any(not t for t in attempts):
            status = "REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE"
        else:
            for speech in attempts:
                try:
                    findings.append(mismatch_details(text,speech))
                except AcousticQAError:
                    findings.append(None)
            if any(x is None for x in findings):
                status = "REVIEW_REQUIRED_BAD_TRANSCRIPT"
            else:
                consensus = mismatch_details(attempts[0],attempts[1])
                if any("[unclear]" in t.lower() or "[inaudible]" in t.lower() for t in attempts):
                    status = "REVIEW_REQUIRED_UNCLEAR_SPEECH"
                else:
                    minor = verified_minor_asr_variation(
                        text,attempts[0],attempts[1],
                        max_difference_fraction=max_difference_fraction)
                    if (consensus["difference_fraction_upper_bound"] >
                            max_difference_fraction and not minor):
                        status = "REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE"
                    elif (any(
                        x["difference_fraction_upper_bound"] > max_difference_fraction or
                        x["sensitive_mismatches"] or x["circa_red_flags"] or
                        x["letter_y_yay_red_flags"] for x in findings
                    ) and not minor):
                        status = "REVIEW_REQUIRED_PRONUNCIATION_RISK"
                    else:
                        status = "ASR_SCREEN_PASS_LISTENING_REQUIRED"
        source_risks=[asdict(x) for x in find_pronunciation_risks(raw_texts[n-1],text)]
        # Two script-blind recognizers may both silently repair an actually
        # mispronounced variable; consensus never cancels source-derived risk.
        if status == "ASR_SCREEN_PASS_LISTENING_REQUIRED" and source_risks:
            status = "REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK"
        rows.append({
            "slide": n, "source_pronunciation_risks":source_risks,
            "audio_sha256": sha256(wav),
            "expected_spoken_sha256": hashlib.sha256(text.encode("utf8")).hexdigest(),
            "transcripts": attempts,
            "assessment": status,
            "comparisons": findings,
        })
    if _input_snapshot(folder,len(expected))!=input_snapshot:
        raise AcousticQAError("Acoustic source bytes changed during recognition; discard all transcripts")
    return {
        "schema_version": 2,
        "input_snapshot_sha256":input_snapshot,
        "recognition_models": list(recognition_models),
        "voice_provenance_sha256": sha256(folder/".microgen_tts_provenance.json"),
        "slide_count": len(rows),
        "slides": rows,
        "review_required_slides": [r["slide"] for r in rows if r["assessment"] != "ASR_SCREEN_PASS_LISTENING_REQUIRED"],
        "risk_review_slides": [r["slide"] for r in rows if r["source_pronunciation_risks"]],
        "unavailable_recognizer_passes": sorted(unavailable_engines),
        # Even a clean ASR screen is not a verified pronunciation or a release pass.
        "human_listening_approved": False,
        "academic_qa_approved": False,
        "element_highlighting_approved": False,
        "publishable": False,
    }


AUDIO_TRANSCRIPT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"transcript": {"type": "string"}},
    "required": ["transcript"],
}


def is_meta_transcript(text: str) -> bool:
    """Detect a reviewer returning its own drafting process, not audible words.

    This never removes text or approves speech. A contaminated result must
    be independently rechecked ONCE, or marked as an untrusted transcript.
    The patterns identify unusual model *editing* phrases and explicit
    correction arrows, not common lecture language ("let us check").
    """
    if not isinstance(text, str):
        return True
    v = text.casefold()
    markers = (
        "let's write it as", "let’s write it as",
        "let's check if there's any other word",
        "let’s check if there’s any other word",
        "let's check if there is any other word",
        "the transcription should be", "my transcription is",
    )
    return any(m in v for m in markers) or (
        ' -> ' in v and ('wait,' in v or 'let' in v))


def parse_blind_audio_transcript_response(raw: str) -> str:
    """Strict Gemini JSON contract; never use a model explanation as audio."""
    if not isinstance(raw, str) or len(raw) > 20000:
        raise AcousticQAError("Independent audio reviewer returned oversized/nontext output")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AcousticQAError("Independent audio reviewer broke JSON transcript contract") from exc
    if (not isinstance(data, dict) or set(data) != {"transcript"}
            or not isinstance(data["transcript"], str)
            or not 5 <= len(data["transcript"].strip()) <= 12000
            or is_meta_transcript(data["transcript"])):
        raise AcousticQAError("Independent reviewer returned invalid or explanatory transcript")
    return data["transcript"].strip()


def gemini_audio_recognizer(api_key: str, *, model: str="gemini-3.5-flash"):
    """Use a separate audio understanding model; never send target script.

    Do not let the independent recognizer see the expected text, as it may
    autocorrect the audible words to the target and mask errors.
    """
    from google import genai
    from google.genai import types
    client = genai.Client(
        api_key=api_key, http_options=types.HttpOptions(timeout=90000)
    )
    prompt = (
        "Transcribe the exact audible words in this English university lecture "
        "recording. Do not infer or fix what the speaker *should* have said. "
        "Preserve odd or unexpected words as actually spoken. Do not "
        "substitute conventional mathematical terminology for what is heard. "
        "Return only words actually heard, no explanations or timecodes. "
        "When unintelligible insert [unclear]. "
        "Respond with only one JSON object containing a transcript string. "
        "Do not include reasoning, draft notes or suggested corrections."
    )
    def transcribe(wav: Path) -> str:
        content = wav.read_bytes()
        if len(content) > 18_000_000:
            raise AcousticQAError("Audio too large to transcribe inline")
        from microgen_tts_service_recovery import (
            run_bounded_recognition, AudioRecognitionUnavailable,
        )
        def single_attempt():
            response = client.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=content,mime_type="audio/wav"),
                          prompt],
                config=types.GenerateContentConfig(
                    temperature=0, max_output_tokens=2400,
                    response_mime_type="application/json",
                    response_json_schema=AUDIO_TRANSCRIPT_SCHEMA,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            return parse_blind_audio_transcript_response(response.text or "")
        try:
            return run_bounded_recognition(single_attempt,time.sleep,max_attempts=3)
        except AudioRecognitionUnavailable:
            raise AcousticQAError("Independent audio transcription unavailable") from None
    return transcribe


def require_external_new_receipt(folder: Path, destination: Path) -> Path:
    """Fail before paid recognition if a receipt could alter source assets."""
    source=Path(folder).resolve(strict=True)
    output=Path(destination).resolve(strict=False)
    if output==source or source in output.parents or output in source.parents:
        raise AcousticQAError("Acoustic evidence must be outside the source lesson tree")
    if output.exists() or output.is_symlink():
        raise AcousticQAError("Refusing to overwrite any prior acoustic evidence")
    if not output.parent.is_dir():
        raise AcousticQAError("Acoustic report parent must already exist")
    return output


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Independent MicroGen TTS acoustic QA")
    parser.add_argument("folder",type=Path,help="Isolated lesson folder with verified WAVs")
    parser.add_argument("--new-report",type=Path,required=True,
                        help="New receipt file OUTSIDE the lesson tree; never overwritten")
    parser.add_argument("--primary-model",default="gemini-3.5-flash")
    parser.add_argument("--secondary-model",default="gemini-3.8-flash")
    parser.add_argument("--max-slides",type=int,default=0,
                        help="0 means all; nonzero for diagnostic scope only")
    args=parser.parse_args(argv)
    # Run all inexpensive destination/preflight checks BEFORE paid model calls.
    out=require_external_new_receipt(args.folder,args.new_report)
    from dotenv import load_dotenv
    from text_to_speech_v25 import normalize_scientific_speech
    from gemini_keys import get_gemini_api_keys
    config = Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "Microvid" / ".env"
    load_dotenv(config,override=False)
    keys=get_gemini_api_keys()
    if not keys: raise AcousticQAError("No configured independent audio model API key")
    sidecar=json.loads((args.folder/"script_tts.json").read_text(encoding="utf8"))
    slides=sidecar.get("slides",[])
    if not slides: raise AcousticQAError("No narration")
    if args.max_slides:
        raise AcousticQAError("Partial transcription is diagnostic only; cannot issue full QA receipt")
    if args.primary_model == args.secondary_model:
        raise AcousticQAError("Two distinct independent audio models required")
    texts=[str(x.get("tts_text") or x["narration"]) for x in slides]
    receipt=audit_with_recognizer(args.folder,texts,
        gemini_audio_recognizer(keys[0],model=args.primary_model),
        normalize_scientific_speech,
        independent_recognizer=gemini_audio_recognizer(keys[0],model=args.secondary_model),
        recognition_models=(args.primary_model,args.secondary_model))
    # Atomic exclusive creation, no writes under lecture source directory.
    with out.open("x",encoding="utf8") as destination:
        destination.write(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"path":str(out),
                      "review_required_slides":receipt["review_required_slides"],
                      "publishable":False},indent=2))
    return 2 if receipt["review_required_slides"] else 0


if __name__=="__main__":
    raise SystemExit(main())
