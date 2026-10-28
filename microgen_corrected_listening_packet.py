"""Source-grounded A/B listening packet for unresolved Thomas §2.5 sound.

Offline, browser-openable audio+PDF previews. This is NOT automated phonetic
or narrator acceptance; verdicts remain blank until human review.
"""
from __future__ import annotations
import csv
import html
import shutil
import wave
from pathlib import Path
import pymupdf as fitz
from microgen_source_safe_orchestrator import verify_workspace,read_json,atomic_json,digest
from microgen_corrected_slide_clock import build_slide_clock

class ListeningPacketError(ValueError):
    pass

RISKS={5:("CDOT","Does 'c' sound like 'circa' instead of its intended variable pronunciation?"),
       6:("CDOT","Is the continuity-test variable 'c' pronounced correctly?"),
       10:("Y_VALUE","Is 'y-value' spoken clearly, without misreading the letter y?")}

def _seconds(wav):
    with wave.open(str(wav),"rb") as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2 or not 8000<=f.getframerate()<=48000:
            raise ListeningPacketError("Unexpected A/B WAV format")
        duration=f.getnframes()/f.getframerate()
        if not .05<=duration<600:raise ListeningPacketError("Invalid comparison WAV")
        return round(duration,6)

def prepare_corrected_pronunciation_packet(recovery,stage,selection,shadow,film,pixel_audit,output):
    rec=Path(recovery).resolve(strict=True)
    stage=Path(stage).resolve(strict=True)
    chosen=Path(selection).resolve(strict=True)
    shadow=Path(shadow).resolve(strict=True)
    video_dir=Path(film).resolve(strict=True)
    checked=Path(pixel_audit).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    plan=build_slide_clock(stage,chosen,shadow)
    srcrec=verify_workspace(rec)
    if srcrec!=plan["source"]:
        raise ListeningPacketError("Recovered original and corrected source differ")
    source=Path(srcrec["source_root"])
    protected=(rec,stage,chosen,shadow,video_dir,checked,source)
    if (dest.exists() or dest.is_symlink() or
            any(dest==p or dest.is_relative_to(p) or p.is_relative_to(dest) for p in protected)):
        raise ListeningPacketError("Unapproved review packet must be a new isolated folder")
    selected=read_json(chosen/"selection_receipt.json")
    prior=read_json(rec/"legacy_mp4_audio_receipt.json")
    pixels=read_json(checked/"pixel_audit_receipt.json")
    vid=video_dir/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4"
    if (selected.get("status")!="SHADOW_ONLY_TRIAL_SELECTION" or
            selected.get("publication_allowed") is not False or
            prior.get("status")!="PROVISIONAL_NOT_PUBLISHABLE" or
            pixels.get("status")!="CORRECTED_SLIDE_PIXEL_AUDIT_PASS_NOT_ACADEMIC" or
            pixels.get("publication_allowed") is not False or
            pixels.get("slide_mapping_technically_verified") is not True or
            pixels.get("sample_count")!=50 or pixels.get("passed_samples")!=50 or
            pixels.get("source_pdf_sha256")!=srcrec["source_pdf_sha256"] or
            pixels.get("source_shadow_wav_sha256")!=digest(plan["shadow_wav"]) or
            vid.is_symlink() or not vid.is_file() or
            pixels.get("video_sha256")!=digest(vid)):
        raise ListeningPacketError("Source-bound corrected video pixel acceptance missing")
    candidates=selected.get("trials")
    if (not isinstance(candidates,list) or len(candidates)!=3 or
            sorted(x.get("slide") for x in candidates)!=[5,6,10]):
        raise ListeningPacketError("Exactly three original-correction pairs required")
    source_script=read_json(source/"script_tts.json")
    slides=source_script.get("slides")
    if not isinstance(slides,list) or len(slides)!=17:
        raise ListeningPacketError("Expected verbatim 17 slide narration")
    pairs=[]
    for row in candidates:
        slide=row["slide"]; risk,question=RISKS[slide]
        original=rec/"audio"/f"slide{slide}.wav"
        correction=chosen/f"slide{slide:02d}_{risk}_UNAPPROVED.wav"
        if (row.get("risk")!=risk or row.get("phonetic_approved") is not False
                or row.get("voice_independently_verified") is not False or
                correction.is_symlink() or not correction.is_file() or
                original.is_symlink() or not original.is_file() or
                row.get("wav_sha256")!=digest(correction) or
                prior["clips"][slide-1]["sha256"]!=digest(original)):
            raise ListeningPacketError("A/B correction provenance changed")
        text=slides[slide-1].get("tts_text") or slides[slide-1].get("narration")
        if not isinstance(text,str) or not text.strip():
            raise ListeningPacketError("Source narration text missing")
        pairs.append({"slide":slide,"risk":risk,"question":question,
                      "original_path":original,"corrected_path":correction,
                      "original_sha":digest(original),"corrected_sha":digest(correction),
                      "original_seconds":_seconds(original),"corrected_seconds":_seconds(correction),
                      "source_narration":text})
    dest.mkdir(parents=True,exist_ok=False)
    try:
        with fitz.open(source/"slides.pdf") as pdf:
            if pdf.page_count!=17:raise ListeningPacketError("PDF source changed")
            for row in pairs:
                i=row["slide"]
                for kind,path in (("original",row["original_path"]),("trial",row["corrected_path"])):
                    target=dest/f"slide{i:02d}_{kind}_UNREVIEWED.wav"
                    shutil.copyfile(path,target)
                    if digest(target)!=row[kind.replace("trial","corrected")+"_sha"]:
                        raise ListeningPacketError("Source WAV changed during comparison copy")
                pix=pdf[i-1].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
                pix.save(dest/f"slide{i:02d}_original_pdf.png")
        # No web dependencies, no automatic saving or pretending review pass.
        cards=[]
        for row in pairs:
            i=row["slide"]
            cards.append(
                f'<article><h2>Slide {i} — {html.escape(row["risk"])}</h2>'
                f'<p><strong>Listening question:</strong> {html.escape(row["question"])}</p>'
                f'<img src="slide{i:02d}_original_pdf.png" alt="Original PDF slide {i}"/>'
                f'<p><strong>Original source-audio reference</strong></p>'
                f'<audio controls preload="none" src="slide{i:02d}_original_UNREVIEWED.wav"></audio>'
                f'<p><strong>Historical corrected trial (unapproved)</strong></p>'
                f'<audio controls preload="none" src="slide{i:02d}_trial_UNREVIEWED.wav"></audio>'
                f'<details><summary>Exact narration script</summary><p>{html.escape(row["source_narration"])}</p></details></article>')
        index='<!doctype html><html lang="en"><meta charset="utf-8"><title>Thomas 2.5 pronunciation — unapproved</title><style>body{font:16px sans-serif;max-width:900px;margin:2rem auto}article{border:1px solid #999;padding:1rem;margin:1rem 0}img{max-width:100%}audio{width:100%}</style><h1>Section 2.5 — source-bound UNAPPROVED listening</h1><p>Compare original and trial audio. The video pixel mapping passed technical QA; neither speech accuracy nor voice identity is confirmed. Record a separate human listening verdict; this page never publishes or accepts automatically.</p>'+''.join(cards)+'</html>'
        (dest/"index.html").write_text(index,encoding="utf8")
        with (dest/"manual_review_template.csv").open("w",encoding="utf8",newline="") as stream:
            writer=csv.writer(stream)
            writer.writerow(["slide","risk","reviewer_verdict","voice_same","notes"])
            for row in pairs:writer.writerow([row["slide"],row["risk"],"UNREVIEWED","UNREVIEWED",""])
        if digest(vid)!=pixels["video_sha256"] or verify_workspace(rec)!=srcrec:
            raise ListeningPacketError("Source drift while constructing review packet")
        manifest={"status":"SOURCE_BOUND_PRONUNCIATION_AB_REVIEW_UNAPPROVED",
                  "source_pdf_sha256":srcrec["source_pdf_sha256"],
                  "script_sha256":srcrec["narration_sha256"],
                  "pixel_audit_sha256":digest(checked/"pixel_audit_receipt.json"),
                  "source_video_sha256":pixels["video_sha256"],
                  "pairs":[{k:v for k,v in row.items() if k not in ("original_path","corrected_path")} for row in pairs],
                  "phonetic_correctness_verified":False,"voice_consistency_verified":False,
                  "mathematical_figure_semantics_verified":False,"publication_allowed":False}
        atomic_json(dest/"listening_packet_receipt.json",manifest)
        return {"review_files":3,"audio_pairs":3,"index":str(dest/"index.html"),
                "manual_review_required":True,"publication_allowed":False}
    except Exception:
        shutil.rmtree(dest)
        raise
