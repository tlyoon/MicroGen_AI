"""Read-only, source-bound Section 2.5 math-letter TTS repair triage.

Distinguishes text-normalized hazards from unverified pronunciation without
promoting ASR guesses or normalization hashes to proof of audible phonemes.
Generated reports are separate from the source folder and are not release gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from microgen_fresh_source_cues import source_inventory
from microgen_source_safe_orchestrator import atomic_json, digest
from microgen_tts_risk_register import find_pronunciation_risks
from microgen_pronunciation import find_issues
from text_to_speech_v25 import normalize_scientific_speech


class PronunciationTriageError(ValueError):
    pass


def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf8")).hexdigest()


def assess_provenance(script, risk, provenance, wav_hashes):
    """Verify all slide identities and TTS inputs, then classify *text* evidence.

    Deliberately does NOT return an acoustic PASS or clear a listening risk.
    """
    slides = script.get("slides")
    risks = risk.get("slides")
    audio = provenance.get("slides")
    n = len(wav_hashes)
    if not all(isinstance(x, list) and len(x) == n for x in (slides, risks, audio)):
        raise PronunciationTriageError("Full slide, risk and WAV inventories required")
    if (risk.get("slide_count") != n or provenance.get("slide_count") != n or
            risk.get("publishable") is not False or
            provenance.get("listening_qa_verified") is not False or
            provenance.get("academic_qa_verified") is not False):
        raise PronunciationTriageError("Untrusted source or previously approved status")
    if not provenance.get("technical_provenance_verified"):
        raise PronunciationTriageError("TTS technical provenance not verified")
    if not provenance.get("provider") or not provenance.get("voice_name"):
        raise PronunciationTriageError("Unpinned TTS provider or voice")

    rows = []
    for position, (item, reg, record, wav_sha) in enumerate(zip(slides, risks, audio, wav_hashes), 1):
        if any(x.get("slide") != position for x in (item, reg, record)):
            raise PronunciationTriageError("Out-of-order slide identity")
        raw = item.get("tts_text")
        if not isinstance(raw, str) or not raw.strip():
            raise PronunciationTriageError("Missing original TTS text")
        spoken = normalize_scientific_speech(raw)
        if (reg.get("tts_source_sha256") != _text_sha(raw) or
                reg.get("spoken_input_sha256") != _text_sha(spoken) or
                record.get("normalized_input_sha256") != _text_sha(spoken) or
                reg.get("audio_wav_sha256") != wav_sha or record.get("sha256") != wav_sha or
                record.get("provider") != provenance["provider"] or
                record.get("voice_name") != provenance["voice_name"]):
            raise PronunciationTriageError("Audio, source or actual synthesized input mismatch")
        expected = find_pronunciation_risks(raw, spoken)
        actual = reg.get("risks")
        if not isinstance(actual, list) or [
            (x.get("code"), x.get("source"), x.get("start"), x.get("end")) for x in actual
        ] != [(x.code, x.source, x.start, x.end) for x in expected]:
            raise PronunciationTriageError("Risk register diverges from current narration")
        residual = find_issues(raw, spoken)
        for hazard in actual:
            code = hazard["code"]
            state = "UNRESOLVED_LISTENING_RISK"
            text_evidence = "No protected normalized phrase verified"
            if code == "math_c_sentence":
                # Count every exact contextual source phrase, not just ANY 'see.'.
                src = hazard["source"]
                m = re.fullmatch(r"(?i)(at|point|approaches|of|equals|variable|constant|coefficient)\s+c\.", src)
                if m is None:
                    raise PronunciationTriageError("Unrecognized math C period expression")
                prefix = m.group(1)
                before = len(re.findall(r"(?i)\b" + re.escape(prefix) + r"\s+c\.(?=\s+[A-Z]|$)", raw))
                after = len(re.findall(r"(?i)\b" + re.escape(prefix) + r"\s+see\.(?=\s+[A-Z]|$)", spoken))
                if before > 0 and after >= before:
                    state = "NORMALIZED_INPUT_VERIFIED_LISTENING_PENDING"
                    text_evidence = "Verified spoken-input SHA and contextual C-to-see coverage"
                else:
                    state = "UNPROTECTED_MATH_C_INPUT"
                    text_evidence = "Contextual C-to-see conversion absent or incomplete"
            if any(problem.code == "ambiguous_math_c_period" for problem in residual):
                if code == "math_c_sentence":
                    state = "PRE-SYNTHESIS_SAFETY_BLOCK"
                    text_evidence = "Residual ambiguous math C period"
            rows.append({
                "slide": position, "risk_code": code,
                "source": hazard["source"], "start": hazard["start"], "end": hazard["end"],
                "triage": state, "text_evidence": text_evidence,
                "wav_sha256": wav_sha, "spoken_input_sha256": _text_sha(spoken),
                "acoustic_approval": False, "publication_allowed": False,
            })
    if len(rows) != risk.get("risk_count"):
        raise PronunciationTriageError("Risk count is inconsistent")
    return {"slide_count": n, "risk_count": len(rows), "by_triage": dict(Counter(x["triage"] for x in rows)),
            "voice_name": provenance["voice_name"], "provider": provenance["provider"],
            "acoustic_approval": False, "publication_allowed": False, "rows": rows}


def build_triage(stage, risk_file, output):
    base = Path(stage).resolve(strict=True)
    risk_path = Path(risk_file).resolve(strict=True)
    dest = Path(output).absolute()
    if (dest.exists() or dest.is_symlink() or dest.is_relative_to(base) or
            base.is_relative_to(dest) or dest.is_relative_to(risk_path.parent)):
        raise PronunciationTriageError("Output must be a new independent directory")
    _, source = source_inventory(base)
    script_path = base / "script_tts.json"
    provenance_path = base / ".microgen_tts_provenance.json"
    script = json.loads(script_path.read_text(encoding="utf8"))
    risk = json.loads(risk_path.read_text(encoding="utf8"))
    prov = json.loads(provenance_path.read_text(encoding="utf8"))
    wav_hashes = [x["wav_sha256"] for x in source["wav_inventory"]]
    report = assess_provenance(script, risk, prov, wav_hashes)
    pinned = {str(p): digest(p) for p in [script_path, provenance_path, risk_path]}
    dest.mkdir(parents=True, exist_ok=False)
    try:
        import shutil
        with (dest / "risk_triage.csv").open("w", encoding="utf-8-sig", newline="") as fp:
            columns = ("slide", "risk_code", "source", "start", "end", "triage",
                       "text_evidence", "wav_sha256", "spoken_input_sha256",
                       "acoustic_approval", "publication_allowed")
            writer = csv.DictWriter(fp, fieldnames=columns)
            writer.writeheader()
            writer.writerows(report["rows"])
        if source_inventory(base)[1] != source or any(digest(p) != sha for p, sha in pinned.items()):
            raise PronunciationTriageError("Sources changed during audit")
        result = {k: v for k, v in report.items() if k != "rows"}
        result.update({
            "source": source, "input_sha256": pinned,
            "triage_csv_sha256": digest(dest / "risk_triage.csv"),
            "semantic_approval": False,
            "verified_scope": "SOURCE_WAV_AND_NORMALIZED_TEXT_ONLY",
            "unverified_scope": ["actual phonemes", "equations", "figure semantics", "element synchronization"],
        })
        atomic_json(dest / "triage_receipt.json", result)
        return result
    except Exception:
        import shutil
        shutil.rmtree(dest)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--risk-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_triage(args.stage, args.risk_file, args.output)
    print(json.dumps({k: result[k] for k in ("slide_count", "risk_count", "by_triage", "publication_allowed")},
                     sort_keys=True))
