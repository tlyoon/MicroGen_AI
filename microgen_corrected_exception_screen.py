"""Offline exception-first, nonpublishing corrected-lesson QA triage.

This is anomaly screening, NOT mathematical/figure semantic validation,
speaker identification, phoneme verification, or a release authorization.
Only source-verified review package content may be read. Exact source
audio remains untouched.
"""
from __future__ import annotations
import csv
import html
import math
import re
import shutil
import wave
from array import array
from difflib import SequenceMatcher
from pathlib import Path

from microgen_corrected_semantic_review import verify_semantic_packet_file_integrity
from microgen_source_safe_orchestrator import atomic_json,digest,read_json


class ExceptionTriageError(ValueError):
    pass


STOP=set("""about after again also among been being both could each even from have here
into just like more only over same should some than that them then there these
they this those through very when where which while with would your such other
because function functions continuous continuity limit limits value values graph
graphs figure diagram slide equation mathematics mathematically mathematical
source shown below above points point""".split())


def normalized_words(s):
    if not isinstance(s,str):raise ExceptionTriageError("Text must be string")
    return re.findall(r"[a-z]+|\d+",s.lower().replace("’","'"))


def lexical_screen(script,recognition):
    """ASR agreement screens possible TTS mismatches, never pronunciation."""
    reference=normalized_words(script)
    observed=[]
    low_conf=0
    for item in recognition:
        if (not isinstance(item,dict) or
                not isinstance(item.get("word"),str) or
                not isinstance(item.get("conf"),(int,float)) or
                not math.isfinite(item["conf"]) or not 0<=item["conf"]<=1):
            raise ExceptionTriageError("Malformed ASR observation")
        observed.extend(normalized_words(item["word"]))
        if item["conf"]<.65:low_conf+=1
    if not reference or not observed:
        return {"word_sequence_similarity":0.0,"asr_word_count":len(observed),
                "low_confidence_words":low_conf,"script_word_count":len(reference)}
    return {"word_sequence_similarity":round(
        SequenceMatcher(None,reference,observed,autojunk=False).ratio(),4),
        "asr_word_count":len(observed),"low_confidence_words":low_conf,
        "script_word_count":len(reference)}


def pcm_risk_screen(wav_file):
    """Numerical loudness/clipping/silence only; cannot determine narrator."""
    samples=0
    power=0
    clipped=0
    quiet=0
    with wave.open(str(wav_file),"rb") as wav:
        if (wav.getnchannels()!=1 or wav.getsampwidth()!=2
                or wav.getframerate() not in (16000,24000,48000)):
            raise ExceptionTriageError("Unexpected mono PCM16 sample rate/format")
        rate=wav.getframerate()
        nominal=wav.getnframes()
        while True:
            chunk=wav.readframes(16000)
            if not chunk:break
            if len(chunk)%2:
                raise ExceptionTriageError("Malformed WAV sample bytes")
            data=array("h")
            data.frombytes(chunk)
            for x in data:
                samples+=1
                power+=x*x
                clipped+=int(abs(x)>=32760)
                quiet+=int(abs(x)<=120)
    if samples<rate//10 or samples!=nominal:
        raise ExceptionTriageError("Incomplete audio WAV frames")
    rms=math.sqrt(power/samples)/32768.0
    return {"samples":samples,"sample_rate_hz":rate,
            "seconds":round(samples/rate,6),
            "rms_dbfs":round(20*math.log10(max(1e-12,rms)),2),
            "near_clip_fraction":round(clipped/samples,6),
            "quiet_sample_fraction":round(quiet/samples,4)}


def _source_text_match(region_text,narration,words):
    # A textual hint, never an equation/narration semantic match.
    terms={x for x in normalized_words(region_text)
           if len(x)>=5 and x not in STOP}
    if not terms:
        return {"distinct_source_terms":0,"narration_overlap":0,
                "asr_overlap":0,"textual_context_hint":False}
    spoken=set(normalized_words(narration))
    observed={token for w in words for token in normalized_words(w["word"])}
    narration_matches=terms & spoken
    asr_matches=terms & observed
    return {"distinct_source_terms":len(terms),
            "narration_overlap":len(narration_matches),
            "asr_overlap":len(asr_matches),
            "textual_context_hint":bool(narration_matches and asr_matches)}


def _risk_label(flags,kind):
    if "KNOWN_PRONUNCIATION_TRIAL_UNAPPROVED" in flags:
        return "REVIEW_FIRST"
    if "ASR_SCRIPT_LOW_AGREEMENT" in flags or "ACOUSTIC_ANOMALY" in flags:
        return "REVIEW_FIRST"
    if kind=="math" and "NO_SHARED_LEXICAL_CONTEXT_FROM_SCRIPT_AND_ASR" in flags:
        return "REVIEW_FIRST"
    return "PENDING_REVIEW"


def _safe_new_output(out,root):
    result=Path(out).resolve(strict=False)
    src=Path(root).resolve(strict=True)
    if (result.exists() or result.is_symlink() or
            result==src or result.is_relative_to(src) or src.is_relative_to(result)):
        raise ExceptionTriageError("Must create an isolated, unused QA destination")
    return result


def screen_corrected_exception_priority(packet,expected_receipt_sha,output):
    """Prioritize, but retain ALL original source region review obligations."""
    src=Path(packet).resolve(strict=True)
    output=_safe_new_output(output,src)
    verified=verify_semantic_packet_file_integrity(
        src,expected_receipt_sha256=expected_receipt_sha)
    record=read_json(src/"semantic_review_receipt.json")
    if (record.get("publication_allowed") is not False
            or record.get("all_mathematical_semantics_verified") is not False
            or record.get("all_figure_spoken_correspondence_verified") is not False
            or record.get("pronunciation_approved") is not False
            or record.get("speaker_identity_approved") is not False
            or len(record.get("slides",[]))!=17):
        raise ExceptionTriageError("Source packet must remain unapproved")
    pinned=digest(src/"semantic_review_receipt.json")
    priority=[]
    slices=[]
    risk_slides={5:"c",6:"c",10:"y-value"}
    for row in record["slides"]:
        i=row["slide"]
        if not isinstance(i,int) or i!=len(slices)+1:
            raise ExceptionTriageError("Out-of-order or missing slide")
        script=row["source_narration"]
        observed=row["asr_observations"]
        match=lexical_screen(script,observed)
        wav=src/row["corrected_wav"]
        if wav.is_symlink() or digest(wav)!=row["corrected_wav_sha256"]:
            raise ExceptionTriageError("Changed corrected audio")
        audio=pcm_risk_screen(wav)
        flags=[]
        if match["script_word_count"]<8:
            flags.append("SHORT_TITLE_NOT_ACOUSTICALLY_RATABLE")
        elif match["word_sequence_similarity"]<.55 or match["asr_word_count"]<8:
            flags.append("ASR_SCRIPT_LOW_AGREEMENT")
        if audio["rms_dbfs"]< -37 or audio["near_clip_fraction"]>.001:
            flags.append("ACOUSTIC_ANOMALY")
        if i in risk_slides:
            flags.append("KNOWN_PRONUNCIATION_TRIAL_UNAPPROVED")
        if audio["sample_rate_hz"]!=16000:
            flags.append("CHANGED_SAMPLE_RATE_AUDIO_CONTINUITY_REVIEW")
        # A slide with *no* detected abnormalities still requires real QA.
        slides_regions=[]
        for region in row["math_candidates"]+row["figure_candidates"]:
            if region.get("semantic_alignment_verified") is True or region.get(
                    "caption_to_spoken_figure_verified") is True:
                raise ExceptionTriageError("Premature semantic approval")
            kind="math" if region["id"].startswith("M-") else "figure"
            if region["slide"]!=i or not (src/region["image"]).is_file():
                raise ExceptionTriageError("Source region and original slide mismatch")
            overlap=(_source_text_match(region["source_text"],script,observed)
                     if kind=="math" else
                     {"textual_context_hint":False,"distinct_source_terms":0,
                      "narration_overlap":0,"asr_overlap":0})
            why=list(flags)
            if kind=="math" and not overlap["textual_context_hint"]:
                why.append("NO_SHARED_LEXICAL_CONTEXT_FROM_SCRIPT_AND_ASR")
            if kind=="figure":
                why.append("FIGURE_NARRATION_SEMANTICS_UNVERIFIED")
            priority.append({"region_id":region["id"],"slide":i,"kind":kind,
                             "review_priority":_risk_label(why,kind),
                             "screening_flags":why,"textual_heuristic_only":overlap,
                             "independent_mathematics_approved":False,
                             "independent_figure_correspondence_approved":False})
            slides_regions.append(region["id"])
        slices.append({"slide":i,"word_screen":match,"acoustic_screen":audio,
                       "risk_flags":flags,"regions":slides_regions,
                       "pronunciation_target":risk_slides.get(i),
                       "phonetic_correctness_verified":False,
                       "single_narrator_verified":False})
    if len(priority)!=record["unreviewed_region_decisions"]:
        raise ExceptionTriageError("Dropped mathematical/figure source candidates")
    # Preserve all 91 decisions even for deferred lower-risk items.
    rank={"REVIEW_FIRST":0,"PENDING_REVIEW":1}
    priority.sort(key=lambda x:(rank[x["review_priority"]],x["slide"],x["region_id"]))
    summary={"schema_version":1,
             "status":"INDEPENDENT_OFFLINE_RISK_SCREEN_NOT_ACADEMIC_APPROVAL",
             "source_semantic_receipt_sha256":pinned,
             "source_pdf_sha256":record["source_pdf_sha256"],
             "corrected_pcm_sha256":record["corrected_pcm_sha256"],
             "slides_scanned":len(slices),"region_decisions_unreviewed":len(priority),
             "review_first":sum(x["review_priority"]=="REVIEW_FIRST" for x in priority),
             "review_pending":sum(x["review_priority"]=="PENDING_REVIEW" for x in priority),
             "source_packet_file_sha_checks":verified["files_checked"],
             "slides":slices,"region_priority":priority,
             "pronunciation_c_y_independently_verified":False,
             "speaker_identification_verified":False,
             "equation_semantic_alignment_verified":False,
             "figure_correspondence_verified":False,
             "no_region_auto_approved":True,
             "publication_allowed":False}
    output.mkdir(parents=True,exist_ok=False)
    try:
        with (output/"exception_priority.csv").open("w",encoding="utf8",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["region_id","slide","kind","priority","screening_flags",
                             "review_verdict","reviewer_notes"])
            for item in priority:
                writer.writerow([item["region_id"],item["slide"],item["kind"],
                                 item["review_priority"],
                                 ";".join(item["screening_flags"]),"UNREVIEWED",""])
        rows=[]
        for item in priority:
            i=item["slide"]
            meta=record["slides"][i-1]
            orig=next(v for v in meta["math_candidates"]+meta["figure_candidates"]
                      if v["id"]==item["region_id"])
            label=html.escape(item["region_id"])
            flags=html.escape(", ".join(item["screening_flags"]) or "No high-priority heuristic")
            # Images/audio are in original SHA-checked packet; relative links
            # target its sibling directory, not browser network resources.
            rel=src.name
            rows.append(
                f'<tr><td>{html.escape(item["review_priority"])}</td>'
                f'<td>{label}</td><td>Slide {i}</td><td>{flags}</td>'
                f'<td><a href="../{html.escape(rel)}/{html.escape(orig["image"])}">source image</a> '
                f'<a href="../{html.escape(rel)}/{html.escape(meta["corrected_wav"])}">corrected audio</a></td></tr>')
        html_text=('<!doctype html><html lang="en"><meta charset="utf-8">'
             '<title>Corrected §2.5 — exception-first UNREVIEWED QA</title>'
             '<style>body{font:15px system-ui;max-width:1100px;margin:2rem auto}'
             'table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #aaa}'
             'tr:nth-child(even){background:#eee}</style>'
             '<h1>Prioritized correction QA — not publication approval</h1>'
             '<p>Risk heuristics prioritize inspection only. Every mathematical/figure '
             'region remains UNREVIEWED; no algorithm establishes speaker or phoneme '
             'identity, correctness or semantic match. The source packet is immutable.</p>'
             '<table><tr><th>Priority</th><th>Region</th><th>Slide</th>'
             '<th>Reason</th><th>Source evidence</th></tr>'
             +''.join(rows)+'</table></html>')
        (output/"index.html").write_text(html_text,encoding="utf8")
        if digest(src/"semantic_review_receipt.json")!=pinned:
            raise ExceptionTriageError("Source receipt mutated during QA screening")
        summary["output_files"]={
            "index.html":digest(output/"index.html"),
            "exception_priority.csv":digest(output/"exception_priority.csv")}
        atomic_json(output/"exception_screen_receipt.json",summary)
        verify_exception_screen_packet(output)
        return {"slides":len(slices),"review_first":summary["review_first"],
                "pending":summary["review_pending"],"total":len(priority),
                "publication_allowed":False}
    except Exception:
        shutil.rmtree(output)
        raise


def verify_exception_screen_packet(directory, *, expected_sha256=None):
    """Check output artifacts have not been altered after the offline QA pass."""
    folder=Path(directory).resolve(strict=True)
    path=folder/"exception_screen_receipt.json"
    if path.is_symlink() or not path.is_file():
        raise ExceptionTriageError("Missing regular screening receipt")
    if expected_sha256 is not None and digest(path)!=expected_sha256:
        raise ExceptionTriageError("External screening receipt SHA mismatch")
    record=read_json(path)
    if (record.get("status")!="INDEPENDENT_OFFLINE_RISK_SCREEN_NOT_ACADEMIC_APPROVAL"
            or record.get("publication_allowed") is not False
            or record.get("no_region_auto_approved") is not True
            or record.get("equation_semantic_alignment_verified") is not False
            or record.get("figure_correspondence_verified") is not False
            or record.get("speaker_identification_verified") is not False
            or record.get("pronunciation_c_y_independently_verified") is not False
            or record.get("review_first",0)+record.get("review_pending",0)
                !=record.get("region_decisions_unreviewed")
            or len(record.get("slides",[]))!=17):
        raise ExceptionTriageError("Incorrect review count or forged screening approval")
    registered=record.get("output_files")
    if not isinstance(registered,dict) or set(registered)!={"index.html","exception_priority.csv"}:
        raise ExceptionTriageError("Missing screening output fingerprint inventory")
    for filename,value in registered.items():
        file=folder/filename
        if file.is_symlink() or not file.is_file() or digest(file)!=value:
            raise ExceptionTriageError("Changed reviewer QA output "+filename)
    present={f.name for f in folder.iterdir() if f.is_file() and not f.is_symlink()}
    if present!={"index.html","exception_priority.csv","exception_screen_receipt.json"}:
        raise ExceptionTriageError("Added/untracked or missing screening file")
    with (folder/"exception_priority.csv").open(encoding="utf8",newline="") as f:
        items=list(csv.DictReader(f))
    if len(items)!=record["region_decisions_unreviewed"] or any(
        x.get("review_verdict")!="UNREVIEWED" for x in items):
        raise ExceptionTriageError("Screening CSV falsely marks independent review as complete")
    return {"screened_regions":len(items),"review_first":record["review_first"],
            "pending_unreviewed":record["review_pending"],
            "publication_allowed":False}
