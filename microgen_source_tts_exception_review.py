"""Current-source TTS pronunciation exception packet, fail-closed and immutable.

Cross-check real 23 WAVs, TTS text hashes, 69 source-positioned risk flags,
and real offline Vosk observations; provide per-slide listening references.
The acoustic transcript NEVER automatically clears or repairs a risk.
"""
from __future__ import annotations
import csv
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

from microgen_source_safe_orchestrator import atomic_json, digest
from microgen_fresh_source_cues import source_inventory, FreshCueError


class RiskPacketError(ValueError):
    pass


def _sha_text(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def build_current_tts_risk_review(stage, risk_file, asr_dir, destination):
    base,source=source_inventory(stage)
    risk_file=Path(risk_file).resolve(strict=True)
    asr_dir=Path(asr_dir).resolve(strict=True)
    out=Path(destination).absolute()
    if (out.exists() or out.is_symlink() or out.is_relative_to(base)
            or base.is_relative_to(out) or out.is_relative_to(asr_dir)):
        raise RiskPacketError("Review destination must be an unused independent path")
    risk=json.loads(risk_file.read_text(encoding="utf8"))
    script=json.loads((base/"script_tts.json").read_text(encoding="utf8"))
    if (risk.get("slide_count")!=source["slide_count"] or
        risk.get("publishable") is not False or
        risk.get("audio_review_completed") is not False or
        not isinstance(risk.get("slides"),list) or
        len(risk["slides"])!=source["slide_count"] or
        not isinstance(script.get("slides"),list) or
        len(script["slides"])!=source["slide_count"]):
        raise RiskPacketError("TTS risk evidence not bound to 23 current slides")
    rows=[]
    observed=[]
    for i in range(1,source["slide_count"]+1):
        sr=risk["slides"][i-1]
        written=script["slides"][i-1]
        if (sr.get("slide")!=i or written.get("slide")!=i or
            sr.get("audio_wav_sha256")!=source["wav_inventory"][i-1]["wav_sha256"]):
            raise RiskPacketError("TTS audio or risk index changed")
        text=written["tts_text"]
        if not isinstance(text,str):
            raise RiskPacketError("TTS input text unavailable")
        if sr.get("tts_source_sha256")!=_sha_text(text):
            raise RiskPacketError("Risk source not equal to source-generated TTS text")
        # The actual spoken input may be explicitly normalized for math symbols.
        # Keep this separate provenance hash rather than falsely equating it to
        # the raw narration. No phonetic correctness is inferred from either.
        recognition=json.loads((asr_dir/f"slide{i:02d}.json").read_text(encoding="utf8"))
        if (recognition.get("slide")!=i or
            recognition.get("wav_sha256")!=sr["audio_wav_sha256"] or
            recognition.get("publication_allowed") is not False):
            raise RiskPacketError("Acoustic observation source not bound")
        words=recognition["recognition"]["words"]
        observed.append({"slide":i,"wav_sha256":sr["audio_wav_sha256"],
                         "asr_sha256":digest(asr_dir/f"slide{i:02d}.json")})
        for j,risk_entry in enumerate(sr["risks"],1):
            lo=risk_entry["start"];hi=risk_entry["end"]
            source_text=risk_entry["source"]
            if (not isinstance(lo,int) or not isinstance(hi,int) or
                not 0<=lo<hi<=len(text) or text[lo:hi]!=source_text):
                raise RiskPacketError("Risk span does not match current spoken text")
            context=text[max(0,lo-65):min(len(text),hi+65)].replace("\n"," ")
            # Whole-slide transcript only: word ASR cannot locate arbitrary math glyphs.
            transcript=" ".join(w["word"] for w in words)
            nearby_confusion=bool(re.search(r"\b(?:circa|circle|sarca|sirka)\b",transcript,re.I))
            rows.append({
              "slide":i,"risk_index":j,"priority":risk_entry["priority"],
              "risk_code":risk_entry["code"],"source":source_text,
              "character_start":lo,"character_end":hi,
              "tts_context":context,
              "asr_transcript_lexical_confusion_hint":nearby_confusion,
              "asr_not_phonetic_proof":True,
              "wav_file":f"review_wavs/slide{i:02d}.wav",
              "wav_sha256":sr["audio_wav_sha256"],
              "review_status":"UNREVIEWED",
              "automatic_correction_performed":False})
    if len(rows)!=risk.get("risk_count"):
        raise RiskPacketError("Risk count changed")
    if sorted(set(r["slide"] for r in rows))!=risk["risk_review_slides"]:
        raise RiskPacketError("Flagged source slides changed")
    if not rows:raise RiskPacketError("Empty review would certify nothing")
    initial={"source":source,"risk_file_sha256":digest(risk_file),
             "script_tts_sha256":digest(base/"script_tts.json"),
             "asr_evidence":observed}
    out.mkdir(parents=True,exist_ok=False)
    try:
        folder=out/"review_wavs"
        folder.mkdir()
        for i in sorted(set(r["slide"] for r in rows)):
            shutil.copy2(base/f"slide{i}.wav",folder/f"slide{i:02d}.wav")
            if digest(folder/f"slide{i:02d}.wav")!=source["wav_inventory"][i-1]["wav_sha256"]:
                raise RiskPacketError("Audio copy failed SHA validation")
        with (out/"pronunciation_risk_review.csv").open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
        html_rows=[]
        for row in rows:
            link=html.escape(row["wav_file"])
            html_rows.append("<tr><td>"+str(row["slide"])+
                 "</td><td>"+html.escape(row["risk_code"])+
                 "</td><td>"+html.escape(row["source"])+
                 "</td><td>"+html.escape(row["tts_context"])+
                 "</td><td><audio controls preload='none' src='"+link+
                 "'></audio></td><td>UNREVIEWED</td></tr>")
        (out/"index.html").write_text(
             "<!doctype html><meta charset='utf-8'><title>Section 2.5 genuine TTS review</title>"
             "<h1>Current TTS risk review — NOT pronunciation certified</h1>"
             "<p>Source-grounded risks, playable actual audio, no automatic repairs.</p>"
             "<table border='1'><tr><th>Slide</th><th>Risk</th><th>Text</th><th>Context</th>"
             "<th>Listen</th><th>Approval</th></tr>"+
             "\n".join(html_rows)+"</table>",encoding="utf8")
        # Check source objects *again* before committing final receipt.
        if (source_inventory(base)[1]!=source or digest(risk_file)!=initial["risk_file_sha256"]
            or digest(base/"script_tts.json")!=initial["script_tts_sha256"]
            or any(digest(asr_dir/f"slide{row['slide']:02d}.json")!=row["asr_sha256"]
                   for row in observed)):
            raise RiskPacketError("Source changed while exporting risk packet")
        receipt={"status":"SOURCE_TTS_PRONUNCIATION_EXCEPTIONS_NOT_ACCEPTED",
                 **initial,"risk_count":len(rows),
                 "risk_slides":sorted(set(r["slide"] for r in rows)),
                 "candidate_lexical_hints":sum(bool(r["asr_transcript_lexical_confusion_hint"]) for r in rows),
                 "csv_sha256":digest(out/"pronunciation_risk_review.csv"),
                 "html_sha256":digest(out/"index.html"),
                 "unreviewed_count":len(rows),
                 "human_listening_approved":False,
                 "phonetic_accuracy_verified":False,
                 "mathematical_accuracy_verified":False,
                 "publication_allowed":False}
        atomic_json(out/"pronunciation_risk_receipt.json",receipt)
        return {"risk_count":len(rows),"risk_slides":len(receipt["risk_slides"]),
                "review_folder":str(out),"publication_allowed":False}
    except Exception:
        shutil.rmtree(out)
        raise


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    for arg in ("stage","risk-file","asr-dir","output"):
        p.add_argument("--"+arg,required=True)
    args=p.parse_args()
    print(build_current_tts_risk_review(args.stage,args.risk_file,args.asr_dir,args.output))
