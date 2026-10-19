"""Conservative, independent acoustic TTS QA for MicroGen_AI.

Independent recognition is a diagnostic signal, not evidence that a word
is phonetically correct. Every candidate remains unpublishable until
human listening review is recorded through the existing release workflow.

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
equals equal zero one two three four five six seven eight nine ten
""".split())

class AcousticQAError(RuntimeError):
    """Missing/unreliable independent verification: fail closed."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[A-Za-z]+|\d+", text.lower()):
        # Orthographic ASR variants are *not* pronunciation errors.
        out.append({"c": "see", "sea": "see", "x": "ex", "why": "y",
                    "twos": "two"}.get(w, w))
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
        significant = bool((set(missing) | set(extra)) & SENSITIVE)
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
                elif consensus["difference_fraction_upper_bound"] > max_difference_fraction:
                    status = "REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE"
                elif any(
                    x["difference_fraction_upper_bound"] > max_difference_fraction or
                    x["sensitive_mismatches"] or x["circa_red_flags"] or
                    x["letter_y_yay_red_flags"]
                    for x in findings
                ):
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
    return {
        "schema_version": 1,
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
        "When unintelligible insert [unclear]."
    )
    def transcribe(wav: Path) -> str:
        content = wav.read_bytes()
        if len(content) > 18_000_000:
            raise AcousticQAError("Audio too large to transcribe inline")
        last_exc = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=content,mime_type="audio/wav"),
                              prompt],
                    config=types.GenerateContentConfig(
                        temperature=0, max_output_tokens=2400,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                spoken = (response.text or "").strip()
                if not spoken:
                    raise AcousticQAError("Audio model returned empty transcription")
                return spoken
            except Exception as exc:
                last_exc = exc
                error_text=str(exc).upper()
                permanent_quota = "QUOTA EXCEEDED" in error_text or "LIMIT: 0" in error_text
                temporary = "503" in error_text or "UNAVAILABLE" in error_text
                if attempt == 2 or permanent_quota or not temporary:
                    break
                time.sleep(1 + attempt * 2)
        raise AcousticQAError(f"Independent audio transcription unavailable ({type(last_exc).__name__})")
    return transcribe


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Independent MicroGen TTS acoustic QA")
    parser.add_argument("folder",type=Path,help="Isolated lesson folder with verified WAVs")
    parser.add_argument("--primary-model",default="gemini-3.5-flash")
    parser.add_argument("--secondary-model",default="gemini-3.8-flash")
    parser.add_argument("--max-slides",type=int,default=0,
                        help="0 means all; nonzero for diagnostic scope only")
    args=parser.parse_args(argv)
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
    out=args.folder/RECEIPT
    if out.exists():
        raise AcousticQAError("Refusing to overwrite prior acoustic QA receipt")
    tmp=args.folder/(RECEIPT+".tmp")
    try:
        tmp.write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding="utf8")
        os.replace(tmp,out)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({"path":str(out),
                      "review_required_slides":receipt["review_required_slides"],
                      "publishable":False},indent=2))
    return 2 if receipt["review_required_slides"] else 0


if __name__=="__main__":
    raise SystemExit(main())
