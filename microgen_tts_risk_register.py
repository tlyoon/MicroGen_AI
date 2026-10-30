"""Source-grounded pronunciation-risk inventory and non-destructive repair plan.

Speech recognition is not a phonetic oracle: some errors are silently
normalized by ASR. A high-risk token therefore stays review-required even
after independently transcribed audio agrees with expected wording.
All evidence here is script-based and must NOT be called proof of an error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = 1
# Case-sensitive literal mathematical variables, not global letter substitution.
_MATH_COMPOUND = re.compile(
    r"(?<![A-Za-z])(?P<variable>[xyXY])\s*[-\u2010-\u2015]\s*"
    r"(?P<noun>values?|axis|axes|intercepts?|coordinates?|components?)\b"
)
_MATH_CDOT = re.compile(
    r"(?P<cue>\b(?:at|point|approaches|of|equals|variable|constant|coefficient)\s+)"
    r"c\.(?=\s+[A-Z]|$)", re.I
)
_RAW_VARIABLE_EXPRESSION = re.compile(
    r"(?<![A-Za-z])(?P<function>[fgh])\s*\(\s*(?P<argument>[xyt])\s*\)"
)
_RAW_SUBSCRIPT = re.compile(r"(?<![A-Za-z])\w+_[A-Za-z0-9]+\b")
_AMBIGUOUS_MATH_ABBR = re.compile(r"\b(?:sin|cos|tan|ln|arcsin|arccos)\b")
_GREEK_SYMBOL = re.compile(r"[αβγθλμρφωσΔΩ]")
_ISOLATED_MATH_LETTER = re.compile(r"\b(?P<letter>[xyc])\b",re.I)
_CONTEXT_CUE = re.compile(
    r"\b(?:function|point|limit|at|variable|axis|value|values|"
    r"derivative|integral|graph|coordinate|equation|equals?|"
    r"approach(?:es|ing)?|continuous|continuity|polynomial|"
    r"root|intercept|defined)\b",re.I
)

@dataclass(frozen=True)
class Risk:
    code: str
    source: str
    start: int
    end: int
    expected_spoken: str | None
    automatic_text_correction: bool
    priority: str
    note: str


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_pronunciation_risks(raw: str, normalized: str) -> list[Risk]:
    """Return deduplicated source-based risks; offsets refer to raw input."""
    risks: list[Risk] = []
    covered: list[tuple[int,int]] = []
    def add(match: re.Match, code: str, expected: str | None,
            auto: bool, note: str):
        span = match.span()
        if any(max(a,span[0]) < min(b,span[1]) for a,b in covered):
            return
        covered.append(span)
        risks.append(Risk(
            code=code,source=match.group(),start=span[0],end=span[1],
            expected_spoken=expected,automatic_text_correction=auto,
            priority="high",note=note,
        ))

    for match in _MATH_COMPOUND.finditer(raw):
        letter = "why" if match["variable"].lower()=="y" else "ex"
        expected=letter+" "+match["noun"].lower()
        add(match,"math_letter_compound",expected,expected in normalized.lower(),
            "Letter name may be heard as a lexical word, e.g. Y as 'yay'.")
    for match in _MATH_CDOT.finditer(raw):
        add(match,"math_c_sentence","see.",bool(re.search(r"\bsee\.(?=\s|$)",normalized)),
            "Letter C at a sentence boundary may be read as 'circa'.")
    for match in _RAW_VARIABLE_EXPRESSION.finditer(raw):
        letters = {"f": "eff", "g": "gee", "h": "aitch",
                   "x": "ex", "y": "why", "t": "tee"}
        expected = letters[match["function"].lower()] + " of " + letters[match["argument"].lower()]
        approved = expected in normalized.lower()
        add(match,"function_argument",expected if approved else None,approved,
            "Simple single-letter function application is expanded only by reviewed TTS notation rules.")
    for match in _RAW_SUBSCRIPT.finditer(raw):
        simple = re.fullmatch(r"(?P<letter>[xyz])_(?P<index>[0-9])", match.group(), re.I)
        expected = None
        if simple:
            names = {"x":"ex","y":"why","z":"zee"}
            digits = ("zero","one","two","three","four","five",
                      "six","seven","eight","nine")
            expected = names[simple["letter"].lower()] + " subscript " + digits[int(simple["index"])]
        approved = bool(expected and expected in normalized.lower())
        add(match,"subscript",expected if approved else None,approved,
            "Single-digit coordinate subscripts have reviewed speech; symbolic/multidigit forms remain unreviewed.")
    for match in _AMBIGUOUS_MATH_ABBR.finditer(raw):
        function = match.group().lower()
        operand = re.match(r"\s*\(\s*([xyt])\s*\)", raw[match.end():])
        phrase = {"sin":"sine", "cos":"cosine",
                  "tan":"tangent", "ln":"natural logarithm"}
        letters = {"x":"ex","y":"why","t":"tee"}
        expected = (phrase[function] + " of " + letters[operand.group(1)]
                    if operand and function in phrase else None)
        approved = bool(expected and expected in normalized.lower())
        add(match,"math_abbreviation",expected if approved else None,approved,
            "Exact parenthesized elementary math form is reviewed; free-text abbreviation remains ambiguous.")
    for match in _GREEK_SYMBOL.finditer(raw):
        add(match,"greek_symbol",None,False,
            "Greek name normalized, but phonetic verification is still required.")
    for match in _ISOLATED_MATH_LETTER.finditer(raw):
        s,e=match.span()
        if any(a<=s and e<=b for a,b in covered):
            continue
        context=raw[max(0,s-55):min(len(raw),e+40)]
        if not _CONTEXT_CUE.search(context):
            continue
        add(match,"standalone_math_letter",None,False,
            "Standalone variable requires human-reviewed letter-name pronunciation.")
    return sorted(risks,key=lambda item:(item.start,item.end,item.code))


def build_risk_register(
    slides: list[dict], normalize: Callable[[str],str],
    durations: list[float] | None=None,
    acoustic_report: dict | None=None,
    wav_sha256: list[str] | None=None,
) -> dict:
    if not isinstance(slides,list) or not slides:
        raise ValueError("Nonempty narration slides required")
    ids=[s.get("slide") for s in slides]
    if ids!=list(range(1,len(slides)+1)):
        raise ValueError("Slide IDs must be contiguous and ordered")
    if durations is not None and (len(durations)!=len(slides) or
                                  any(not isinstance(d,(int,float)) or d<=0 for d in durations)):
        raise ValueError("Measured positive durations must cover every slide")
    if wav_sha256 is not None and (len(wav_sha256)!=len(slides) or any(
         not re.fullmatch(r"[a-f0-9]{64}",digest) for digest in wav_sha256)):
        raise ValueError("WAV checksum inventory must cover all numbered slides")
    if acoustic_report is not None:
        if acoustic_report.get("slide_count")!=len(slides):
            raise ValueError("Acoustic report and narration slide count mismatch")
        if [x.get("slide") for x in acoustic_report.get("slides",[])]!=ids:
            raise ValueError("Acoustic report slide identity mismatch")
    entries=[]
    elapsed=0.0
    for i, slide in enumerate(slides):
        raw=str(slide.get("tts_text") or slide.get("narration") or "")
        normalized=normalize(raw)
        risks=find_pronunciation_risks(raw,normalized)
        audio_entry=acoustic_report["slides"][i] if acoustic_report else None
        status=audio_entry.get("assessment") if audio_entry else "ACOUSTIC_SCREEN_NOT_RUN"
        if risks:
            status="REVIEW_REQUIRED_PRONUNCIATION_RISK"
        elif status=="ASR_SCREEN_PASS_LISTENING_REQUIRED":
            status="LISTENING_REVIEW_REQUIRED"
        line={
          "slide":ids[i],
          "tts_source_sha256":_sha(raw),
          "spoken_input_sha256":_sha(normalized),
          "audio_wav_sha256":wav_sha256[i] if wav_sha256 else None,
          "slide_start_seconds":round(elapsed,6) if durations else None,
          "slide_end_seconds":round(elapsed+durations[i],6) if durations else None,
          "risks":[asdict(r) for r in risks],
          "acoustic_assessment":audio_entry.get("assessment") if audio_entry else None,
          "review_status":status,
          "repair_actions":[{
              "risk_code":item.code,
              "source":item.source,
              "expected_spoken":item.expected_spoken,
              "action":(
                  "REGENERATE_WITH_EXISTING_REVIEWED_NORMALIZATION_IN_ISOLATED_STAGE"
                  if item.automatic_text_correction
                  else "REVIEW_AND_AUTHOR_EXPLICIT_TTS_ONLY_TEXT_BEFORE_SYNTHESIS"
              ),
              "publishable":False,
              "required_followup":(
                  "Verify one voice and audio hash; rerun acoustic comparisons; "
                  "obtain human listening and separate academic/highlight approvals."
              ),
          } for item in risks],
        }
        entries.append(line)
        if durations:
            elapsed+=durations[i]
    return {
      "schema_version":SCHEMA_VERSION,
      "slide_count":len(slides),
      "slides":entries,
      "risk_count":sum(len(x["risks"]) for x in entries),
      "risk_review_slides":[x["slide"] for x in entries if x["risks"]],
      "suggested_isolated_repair_slides":[x["slide"] for x in entries if any(
         action["action"].startswith("REGENERATE_WITH") for action in x["repair_actions"])],
      "review_required_slides":[x["slide"] for x in entries
                                if x["review_status"] not in ("",)],
      "audio_review_completed":False,
      "publishable":False,
      "note":"No transcript match can automatically override a source-derived pronunciation risk.",
    }


def save_immutable_risk_report(folder: Path, report: dict) -> Path:
    """Store an immutable, content-addressed QA record; never overwrite."""
    folder=Path(folder)
    if not folder.is_dir():
        raise ValueError("Risk report directory must already exist")
    content=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    hash_prefix=hashlib.sha256(content).hexdigest()[:24]
    path=folder/f"pronunciation-risk-{hash_prefix}.json"
    if path.exists() or path.is_symlink():
        if path.is_file() and path.read_bytes()==content:
            return path
        raise ValueError("Existing immutable risk record differs")
    # Exclusive creation refuses accidental overwrite, even across workers.
    with path.open("xb") as stream:
        stream.write(content)
    return path


def durations_from_wavs(stage: Path, slides_count: int) -> list[float]:
    result=[]
    for index in range(1,slides_count+1):
        p=stage/f"slide{index}.wav"
        with wave.open(str(p),"rb") as w:
            if w.getnframes()<=0 or w.getframerate()<=0:
                raise ValueError(f"Invalid audio: {p}")
            result.append(w.getnframes()/w.getframerate())
    return result


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Read-only TTS pronunciation risk inventory")
    parser.add_argument("sidecar",type=Path,help="path to script_tts.json")
    parser.add_argument("--audio-folder",type=Path,
                        help="optional same-lecture WAV folder to calculate slide-level timing")
    parser.add_argument("--report",type=Path,
                        help="optional NEW risk report path, not overwritten")
    args=parser.parse_args(argv)
    from text_to_speech_v25 import normalize_scientific_speech
    slides=json.loads(args.sidecar.read_text(encoding="utf-8"))["slides"]
    durations=durations_from_wavs(args.audio_folder,len(slides)) if args.audio_folder else None
    audio_hashes=[hashlib.sha256((args.audio_folder/f"slide{i}.wav").read_bytes()).hexdigest()
                  for i in range(1,len(slides)+1)] if args.audio_folder else None
    result=build_risk_register(slides,normalize_scientific_speech,durations,
                               wav_sha256=audio_hashes)
    if args.report:
        if args.report.exists() or args.report.is_symlink():
            parser.error("Refusing to overwrite an existing report")
        args.report.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
        print(f"Report created: {args.report}")
    else:
        print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
