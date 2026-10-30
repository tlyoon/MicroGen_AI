"""Reusable conservative, source-bound TTS pronunciation QA/repair.

Distinguishes deterministic *text* normalization from evidence of correct audio.
Only reviewed, unambiguous notation expansions can be staged automatically.
Independent ASR raises targeted error signals and possible repairs; it cannot
prove phonemes or certify formal publication. No TTS/API calls in this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

DEFAULT_GLOSSARY = Path(__file__).parent / "docs" / "tts_conservative_math_expansions_v2.json"


class PronunciationClosedLoopError(ValueError):
    pass


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _letter(ch: str) -> str:
    return {"x": "ex", "y": "why", "t": "tee", "f": "eff",
            "g": "gee", "h": "aitch", "z": "zee"}.get(ch.lower(), ch)


def _expand(match: re.Match, rule: dict) -> str:
    kind = rule["replacement_kind"]
    if kind == "math_function":
        fname = {"sin": "sine", "cos": "cosine", "tan": "tangent",
                 "ln": "natural logarithm"}[match["function"].lower()]
        return fname + " of " + _letter(match["variable"])
    if kind == "function_argument":
        return _letter(match["function"]) + " of " + _letter(match["variable"])
    if kind == "technical_term":
        return rule["spoken_form"]
    if kind == "numeric_subscript":
        number = {"0": "zero", "1": "one", "2": "two", "3": "three",
                  "4": "four", "5": "five", "6": "six", "7": "seven",
                  "8": "eight", "9": "nine"}[match["index"]]
        return _letter(match["variable"]) + " subscript " + number
    raise PronunciationClosedLoopError("Unknown replacement operation")


def load_glossary(path: Path = DEFAULT_GLOSSARY) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 2 or not isinstance(data.get("rules"), list):
        raise PronunciationClosedLoopError("Glossary must use versioned schema 2")
    ids: set[str] = set()
    safe = []
    for rule in data["rules"]:
        if (not isinstance(rule, dict) or rule.get("id") in ids or
                not isinstance(rule.get("id"), str) or
                rule.get("safety") != "conservative_math_notation" or
                rule.get("replacement_kind") not in (
                    "math_function", "function_argument", "numeric_subscript",
                    "technical_term"
                ) or not isinstance(rule.get("regex"), str) or
                len(rule["regex"]) > 250):
            raise PronunciationClosedLoopError("Unreviewed/duplicate unsafe rule")
        ids.add(rule["id"])
        compiled = re.compile(rule["regex"], re.I if rule.get("case_insensitive") else 0)
        required = {
            "math_function": {"function", "variable"},
            "function_argument": {"function", "variable"},
            "numeric_subscript": {"variable", "index"},
            "technical_term": set(),
        }[rule["replacement_kind"]]
        if rule["replacement_kind"] == "technical_term":
            speech = rule.get("spoken_form")
            evidence = rule.get("reviewed_evidence_sha256")
            if (not isinstance(speech, str) or
                    not re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+){0,10}", speech) or
                    not isinstance(evidence, str) or
                    not re.fullmatch(r"[a-f0-9]{64}", evidence) or
                    not rule.get("examples") or not rule.get("negative_examples")):
                raise PronunciationClosedLoopError("Technical pronunciation needs reviewed evidence and safe speech")
        if not required.issubset(compiled.groupindex):
            raise PronunciationClosedLoopError("Missing required named groups in glossary regex")
        for text in rule.get("examples", []):
            m = compiled.search(text)
            if not m:
                raise PronunciationClosedLoopError(f"Rule misses reviewed example {rule['id']}")
            _expand(m, rule)
        for text in rule.get("negative_examples", []):
            if compiled.search(text):
                raise PronunciationClosedLoopError(f"Rule is overbroad: {rule['id']}")
        safe.append({**rule, "_compiled": compiled})
    if len(safe) < 3:
        raise PronunciationClosedLoopError("Insufficient reviewed rule coverage")
    return safe


def expand_unambiguous_math(text: str, *, glossary: list[dict] | None = None) -> str:
    """Idempotent, minimal spoken-only mathematical notation transformations."""
    out = str(text or "")
    rules = load_glossary() if glossary is None else glossary
    for rule in rules:
        out = rule["_compiled"].sub(lambda m: _expand(m, rule), out)
    return out


def _word(word: str) -> str:
    # Preserve numerical math tokens: deleting digits would fabricate blank
    # alignment words and falsely inflate technical-term pronunciation alerts.
    val = re.sub(r"[^a-z0-9]", "", str(word).casefold())
    if len(val) == 1 and val in "0123456789":
        return ("zero", "one", "two", "three", "four",
                "five", "six", "seven", "eight", "nine")[int(val)]
    # Longer numbers are intentionally left as numeric strings. Their spoken
    # forms are context-dependent and must not be guessed or auto-repaired.
    return {"sea": "see", "cee": "see", "y": "why", "x": "ex"}.get(val, val)


def screen_audio(expected: str, observation: dict | None,
                 wav_sha256: str | None) -> dict:
    """Find broad mismatches but auto-repair only known evidence-backed triggers."""
    if observation is None:
        return {"status": "AUDIO_NOT_SCREENED", "word_mismatches": [],
                "high_confidence_flags": [], "acoustic_approved": False}
    if (not isinstance(observation, dict) or
            not re.fullmatch(r"[a-f0-9]{64}", str(wav_sha256)) or
            observation.get("source_wav_sha256") != wav_sha256 or
            observation.get("phonetic_identity_verified") is not False or
            observation.get("semantic_word_alignment_certified") is not False):
        raise PronunciationClosedLoopError("Offline recognition must be SHA-bound and unapproved")
    rows = observation.get("words")
    if not isinstance(rows, list) or len(rows) > 1000:
        raise PronunciationClosedLoopError("Invalid recognition word rows")
    heard = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("word"), str)
                or type(row.get("conf")) not in (float, int)
                or not 0 <= row["conf"] <= 1):
            raise PronunciationClosedLoopError("Invalid recognition confidence")
        heard.append((_word(row["word"]), row["conf"]))
    expected_tokens = [_word(x) for x in re.findall(r"[A-Za-z]+|\d+", expected)]
    observed = [x[0] for x in heard]
    if not expected_tokens:
        raise PronunciationClosedLoopError("No normalized speech to compare")
    ops = SequenceMatcher(a=expected_tokens, b=observed, autojunk=False).get_opcodes()
    mismatches = []
    for tag, a, b, c, e in ops:
        if tag != "equal":
            mismatches.append({"kind": tag,
                "expected": expected_tokens[a:b], "recognized": observed[c:e]})
    flags = []
    # Check only word *substitutions aligned to the expected letter*, never
    # an unrelated "circa" or "yay" elsewhere in the same narration.
    for tag, a, b, c, e in ops:
        if tag == "equal":
            continue
        missing = set(expected_tokens[a:b])
        for word, confidence in heard[c:e]:
            if confidence < 0.65:
                continue
            if word == "circa" and "see" in missing:
                flags.append({"code": "math_letter_c_circa", "confidence": confidence})
            if word == "yay" and "why" in missing:
                flags.append({"code": "math_letter_y_yay", "confidence": confidence})
    return {"status": "OFFLINE_ASR_SCREEN_ONLY",
            "word_mismatches": mismatches, "high_confidence_flags": flags,
            "acoustic_approved": False}


def plan_slide_repairs(slides: list[dict], normalize: Callable[[str], str],
                       *, observations: list[dict | None] | None = None,
                       wav_hashes: list[str | None] | None = None) -> dict:
    """Plan selective changes. Uncertain audio *never* becomes pass or auto fix."""
    if not slides:
        raise PronunciationClosedLoopError("Nonempty slide list required")
    if (observations is None) != (wav_hashes is None):
        raise PronunciationClosedLoopError("Actual WAV hashes and ASR must be supplied together")
    if observations is not None and (len(observations) != len(slides)
                                   or len(wav_hashes) != len(slides)):
        raise PronunciationClosedLoopError("One ASR/WAV identity required per slide")
    from microgen_pronunciation import find_issues
    from microgen_tts_risk_register import find_pronunciation_risks

    all_rows = []
    prior_ids = set()
    for i, slide in enumerate(slides):
        n = slide.get("slide", i + 1)
        if type(n) is not int or n < 1 or n in prior_ids:
            raise PronunciationClosedLoopError("Invalid or duplicate slide number")
        prior_ids.add(n)
        raw = str(slide.get("tts_text") or slide.get("narration") or "")
        if not raw:
            raise PronunciationClosedLoopError("Empty narration")
        spoken = normalize(raw)
        issues = find_issues(raw, spoken)
        source_risks = find_pronunciation_risks(raw, spoken)
        observation = observations[i] if observations is not None else None
        screening = screen_audio(
            spoken, observation,
            wav_hashes[i] if wav_hashes is not None else None,
        )
        repairs = []
        for risk in source_risks:
            if risk.automatic_text_correction and risk.expected_spoken:
                repairs.append({"source": risk.source, "code": risk.code,
                                "action": "TEXT_NORMALIZATION_ALREADY_APPLIED",
                                "expected": risk.expected_spoken})
            else:
                repairs.append({"source": risk.source, "code": risk.code,
                                "action": "UNRESOLVED_REVIEW_ONLY", "expected": None})
        eligible = (bool(screening["high_confidence_flags"]) and not issues and
                    any(r.code in ("math_letter_compound", "math_c_sentence")
                        and r.automatic_text_correction for r in source_risks))
        if eligible:
            repairs.append({"action": "BOUNDED_ISOLATED_REGENERATION_ELIGIBLE",
                            "reason": "Known bad recognizer word in source-grounded context; new WAV must be independently rechecked"})
        all_rows.append({
            "slide": n, "source_sha256": sha_text(raw),
            "tts_input_sha256": sha_text(spoken),
            "tts_text": spoken,
            "text_was_normalized": spoken != raw,
            "source_risks": len(source_risks),
            "unresolved_preflight_issues": [x.code for x in issues],
            "screening": screening,
            "repair_actions": repairs,
            "bounded_diagnostic_candidate": eligible and len(spoken) <= 500,
            "needs_followup": bool(source_risks or screening["word_mismatches"] or issues),
            "publication_allowed": False,
        })
    return {
        "schema_version": 1, "status": "AUTOMATED_TEXT_REPAIR_PLAN_NOT_FINAL_PHONETIC_QA",
        "slide_count": len(all_rows), "slides": all_rows,
        "selective_diagnostic_slides": [x["slide"] for x in all_rows
                                       if x["bounded_diagnostic_candidate"]],
        "source_narration_unchanged": True,
        "formal_cloud_provider_selected": False,
        "phonetic_identity_verified": False, "publication_allowed": False,
    }


def write_immutable_plan(out: Path, plan: dict) -> Path:
    file = Path(out)
    if any(part.casefold() == "my drive" for part in file.parts):
        raise PronunciationClosedLoopError("QA reports must remain outside protected Drive")
    if file.is_symlink() or file.exists():
        raise PronunciationClosedLoopError("Do not overwrite prior QA plan")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
    return file

def run_isolated_diagnostic_repairs(plan: dict, destination: Path, *,
                                    max_requests: int = 2,
                                    cloud_runner=None) -> dict:
    """Execute ONLY small, evidence-backed and source-grounded diagnostics.

    Does not touch any lecture WAV, choose the formal provider or approve audio.
    Explicit invocation can incur at most max_requests Cloud diagnostic calls.
    """
    if type(max_requests) is not int or not 1 <= max_requests <= 2:
        raise PronunciationClosedLoopError("At most two bounded diagnostic requests")
    folder = Path(destination).resolve(strict=False)
    if (folder.exists() or folder.is_symlink() or
            "diagnostic" not in folder.name.casefold() or
            any(x.casefold() == "my drive" for x in folder.parts)):
        raise PronunciationClosedLoopError("New separate local diagnostic parent required")
    candidates = [row for row in plan.get("slides", [])
                  if row.get("bounded_diagnostic_candidate")]
    if len(candidates) > max_requests:
        raise PronunciationClosedLoopError(
            "More suspected slides than bounded budget: split into separate explicit invocations"
        )
    if not candidates:
        return {"status": "NO_HIGH_CONFIDENCE_DIAGNOSTIC_REPAIR_NEEDED",
                "calls": 0, "publication_allowed": False}
    # All checks happen before first paid request. Never create production files.
    from microgen_pronunciation import require_safe_speech
    for row in candidates:
        spoken = row["tts_text"]
        if not 1 <= len(spoken) <= 500:
            raise PronunciationClosedLoopError("Full narration exceeds bounded diagnostic limits")
        if not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"]):
            raise PronunciationClosedLoopError("Source SHA missing")
        require_safe_speech(spoken, spoken)
    if cloud_runner is None:
        from microgen_cloud_tts_diagnostic import run_diagnostic
        cloud_runner = run_diagnostic
    folder.mkdir(parents=True, exist_ok=False)
    results = []
    for row in candidates:
        target = folder / f"slide_{row['slide']}_diagnostic_auto_repair"
        receipt = cloud_runner(row["tts_text"], target, confirm_chargeable=True)
        if receipt.get("publication_allowed") is not False:
            raise PronunciationClosedLoopError("Diagnostic provider returned an unsafe receipt")
        results.append({"slide": row["slide"], "diagnostic_directory": str(target),
                        "wav_sha256": receipt.get("wav_sha256"),
                        "status": "NEW_DIAGNOSTIC_WAV_NEEDS_INDEPENDENT_RECOGNITION"})
    return {"status": "BOUNDED_DIAGNOSTIC_REPAIR_WAVS_CREATED",
            "calls": len(results), "results": results,
            "same_voice_acoustic_identity_verified": False,
            "phonetic_identity_verified": False, "publication_allowed": False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Source-bound lecture-wide pronunciation screening and isolated repair plan"
    )
    parser.add_argument("--script-tts", type=Path, required=True)
    parser.add_argument("--new-plan", type=Path, required=True)
    parser.add_argument("--wav-folder", type=Path)
    parser.add_argument("--offline-asr-dir", type=Path)
    parser.add_argument("--execute-bounded-diagnostics", type=Path,
                        help="Explicitly run at most 2 authorized Cloud troubleshooting calls in a NEW local diagnostic folder")
    options = parser.parse_args(argv)
    if bool(options.wav_folder) != bool(options.offline_asr_dir):
        parser.error("Use --wav-folder and --offline-asr-dir together")
    source = options.script_tts
    if source.is_symlink() or not source.is_file():
        raise PronunciationClosedLoopError("Authoritative narration JSON missing")
    src_sha = sha_file(source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    slides = payload["slides"]
    observations = []
    hashes = []
    if options.wav_folder:
        root = options.wav_folder.resolve(strict=True)
        asr_dir = options.offline_asr_dir.resolve(strict=True)
        for item in slides:
            n = item["slide"]
            recording = root / f"slide{n}.wav"
            evidence = asr_dir / f"slide{n:02d}.json"
            if (recording.is_symlink() or evidence.is_symlink()
                    or not recording.is_file() or not evidence.is_file()):
                raise PronunciationClosedLoopError("Incomplete WAV/ASR slide inventory")
            h = sha_file(recording)
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if data.get("wav_sha256") != h or data.get("slide") != n:
                raise PronunciationClosedLoopError("Real WAV and offline recognizer hash mismatch")
            hashes.append(h)
            observations.append(data["recognition"])
    from text_to_speech_v25 import normalize_scientific_speech
    plan = plan_slide_repairs(
        slides, normalize_scientific_speech,
        observations=observations if options.wav_folder else None,
        wav_hashes=hashes if options.wav_folder else None
    )
    plan["original_script_sha256"] = src_sha
    if sha_file(source) != src_sha:
        raise PronunciationClosedLoopError("Source narration changed during read-only audit")
    write_immutable_plan(options.new_plan, plan)
    if options.execute_bounded_diagnostics:
        outcome = run_isolated_diagnostic_repairs(plan, options.execute_bounded_diagnostics)
        print(json.dumps(outcome, ensure_ascii=False))
    print(json.dumps({
        "status": plan["status"], "slides": plan["slide_count"],
        "bounded_diagnostic_candidates": plan["selective_diagnostic_slides"],
        "publication_allowed": False
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
