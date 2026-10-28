"""Corrected-course offline PCM junction screening, no speaker-ID or approval.

Source-bound, nonpublishing waveform examination of all 16 neighboring
lecture slide audio boundaries, independent of subjective listening claims.
"""
from __future__ import annotations
import csv
import math
import shutil
import sys
import wave
from array import array
from pathlib import Path
from statistics import median

from microgen_corrected_semantic_review import verify_semantic_packet_file_integrity
from microgen_source_safe_orchestrator import atomic_json,digest,read_json


class BoundaryScreenError(ValueError):
    pass


def _db(samples):
    if not samples:return -120.0
    value=math.sqrt(sum(x*x for x in samples)/len(samples))/32768.
    return round(20*math.log10(max(value,1e-12)),2)


def inspect_clip(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file():
        raise BoundaryScreenError("Missing or symlinked source audio")
    with wave.open(str(p),"rb") as wav:
        rate=wav.getframerate()
        if (wav.getnchannels()!=1 or wav.getsampwidth()!=2
                or rate not in (16000,24000,48000)):
            raise BoundaryScreenError("Unsupported clip audio properties")
        count=wav.getnframes()
        raw=wav.readframes(count)
    if len(raw)!=count*2 or count<rate//10 or count>=600*rate:
        raise BoundaryScreenError("Source audio sample count invalid")
    samples=array("h")
    samples.frombytes(raw)
    if sys.byteorder!="little":samples.byteswap()
    interval=rate//20  # 50 ms
    windows=[]
    for i in range(0,len(samples),interval):
        chunk=samples[i:i+interval]
        if len(chunk)>=interval//2:
            windows.append(_db(chunk))
    voiced=[v for v in windows if v>-38]
    first=list(samples[:rate//10])
    last=list(samples[-rate//10:])
    return {"sample_rate_hz":rate,"samples":count,"seconds":round(count/rate,6),
            "median_voiced_dbfs":median(voiced) if voiced else -120.0,
            "start_100ms_dbfs":_db(first),"end_100ms_dbfs":_db(last),
            "start_sample":int(samples[0]),"end_sample":int(samples[-1]),
            "near_clip_windows":sum(v>-1 for v in windows),
            "silent_window_fraction":round(sum(v<-50 for v in windows)/len(windows),4),
            "sha256":digest(p)}


def scan_neighboring_clip_boundaries(
        packet,expected_receipt_sha256,output):
    original=Path(packet).resolve(strict=True)
    output=Path(output).resolve(strict=False)
    if (output.exists() or output.is_symlink()
            or output==original or output.is_relative_to(original)
            or original.is_relative_to(output)):
        raise BoundaryScreenError("Independent unused output directory required")
    proof=verify_semantic_packet_file_integrity(
        original,expected_receipt_sha256=expected_receipt_sha256)
    meta=read_json(original/"semantic_review_receipt.json")
    if (meta.get("publication_allowed") is not False or
            meta.get("all_mathematical_semantics_verified") is not False or
            meta.get("speaker_identity_approved") is not False or
            meta.get("pronunciation_approved") is not False or
            len(meta.get("slides",[]))!=17):
        raise BoundaryScreenError("Source reviewer packet must stay unapproved")
    clips=[]
    for i,item in enumerate(meta["slides"],1):
        if item.get("slide")!=i:
            raise BoundaryScreenError("Out-of-order audio source slide")
        file=original/item["corrected_wav"]
        if digest(file)!=item["corrected_wav_sha256"]:
            raise BoundaryScreenError("Source WAV changed")
        clips.append(inspect_clip(file))
    trials={5,6,10}
    result=[]
    for i in range(16):
        a,b=clips[i],clips[i+1]
        edge_delta=round(abs(a["end_sample"]-b["start_sample"])/32768.,5)
        rate_change=a["sample_rate_hz"]!=b["sample_rate_hz"]
        level_delta=round(abs(a["median_voiced_dbfs"]-b["median_voiced_dbfs"]),2)
        risk=[]
        if i+1 in trials or i+2 in trials:
            risk.append("PRONUNCIATION_TRIAL_ADJACENCY")
        if rate_change:risk.append("PCM_SAMPLE_RATE_TRANSITION")
        if edge_delta>.12:
            risk.append("POSSIBLE_JUNCTION_CLICK_SAMPLE_JUMP")
        if level_delta>7.5:
            risk.append("POSSIBLE_LOUDNESS_CONTRAST")
        if (a["end_100ms_dbfs"]>-24 and
                b["start_100ms_dbfs"]>-24 and edge_delta>.06):
            risk.append("POSSIBLE_AUDIBLE_NO_FADE_SEAM")
        result.append({"from_slide":i+1,"to_slide":i+2,
                       "from_wav_sha256":a["sha256"],
                       "to_wav_sha256":b["sha256"],
                       "from_sample_rate_hz":a["sample_rate_hz"],
                       "to_sample_rate_hz":b["sample_rate_hz"],
                       "loudness_median_delta_db":level_delta,
                       "edge_sample_absolute_jump":edge_delta,
                       "risk_flags":risk,"requires_review":bool(risk),
                       "voice_identity_verified":False,
                       "phonetic_accuracy_verified":False})
    high=[r for r in result if r["risk_flags"]]
    output.mkdir(parents=True,exist_ok=False)
    try:
        csvfile=output/"boundary_review.csv"
        with csvfile.open("w",encoding="utf8",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["boundary","flags","absolute_edge_jump","voiced_db_difference",
                             "review_verdict","notes"])
            for row in result:
                writer.writerow([f'{row["from_slide"]}->{row["to_slide"]}',
                                 ";".join(row["risk_flags"]),
                                 row["edge_sample_absolute_jump"],
                                 row["loudness_median_delta_db"],"UNREVIEWED",""])
        packet_report={
            "schema_version":1,
            "status":"CORRECTED_PCM_BOUNDARY_RISK_NOT_SPEAKER_IDENTIFICATION",
            "source_semantic_receipt_sha256":expected_receipt_sha256,
            "source_pdf_sha256":meta["source_pdf_sha256"],
            "corrected_pcm_sha256":meta["corrected_pcm_sha256"],
            "source_files_verified":proof["files_checked"],
            "slide_count":17,"boundary_count":16,
            "boundaries_requiring_priority_review":len(high),
            "slide_audio":clips,"boundaries":result,
            "voice_identity_verified":False,
            "phonetic_correctness_verified":False,
            "academic_figure_equation_quality_verified":False,
            "publication_allowed":False,
            "generated_csv_sha256":digest(csvfile)}
        atomic_json(output/"boundary_screen_receipt.json",packet_report)
        if digest(original/"semantic_review_receipt.json")!=expected_receipt_sha256:
            raise BoundaryScreenError("Source receipt changed during boundary processing")
        return {"slides":17,"boundaries":16,"flagged":len(high),
                "publication_allowed":False}
    except Exception:
        shutil.rmtree(output)
        raise


def verify_boundary_screen(folder,expected_receipt_sha256):
    directory=Path(folder).resolve(strict=True)
    receipt=directory/"boundary_screen_receipt.json"
    if receipt.is_symlink() or digest(receipt)!=expected_receipt_sha256:
        raise BoundaryScreenError("Externally pinned review receipt SHA mismatch")
    data=read_json(receipt)
    csvfile=directory/"boundary_review.csv"
    if (data.get("status")!="CORRECTED_PCM_BOUNDARY_RISK_NOT_SPEAKER_IDENTIFICATION"
            or data.get("boundary_count")!=16 or data.get("slide_count")!=17
            or len(data.get("boundaries",[]))!=16
            or data.get("voice_identity_verified") is not False
            or data.get("phonetic_correctness_verified") is not False
            or data.get("publication_allowed") is not False
            or csvfile.is_symlink() or not csvfile.is_file()
            or data.get("generated_csv_sha256")!=digest(csvfile)
            or set(p.name for p in directory.iterdir())!=
               {"boundary_screen_receipt.json","boundary_review.csv"}):
        raise BoundaryScreenError("Changed or falsely approved junction report")
    with csvfile.open("r",encoding="utf8",newline="") as f:
        reviews=list(csv.DictReader(f))
    if len(reviews)!=16 or any(row["review_verdict"]!="UNREVIEWED" for row in reviews):
        raise BoundaryScreenError("Junction reviews must remain unreviewed")
    return {"boundaries_verified":16,"publication_allowed":False}
