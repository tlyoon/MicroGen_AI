"""Source-bound corrected §2.5 equation/figure/audio review handoff.

This creates *evidence for* independent academic and listening review, not
an automated claim that an equation, image, narration or highlight is correct.
No remote model, API, publication, source edits or inherited approvals.
"""
from __future__ import annotations

import collections
import csv
import html
import math
import re
import shutil
from pathlib import Path

import pymupdf as fitz

from microgen_corrected_slide_clock import build_slide_clock
from microgen_audio_cue_binding import validate_audio_bound_cues
from microgen_equation_geometry import equation_region_inventory
from microgen_figure_geometry_inventory import figure_region_inventory
from microgen_figure_pixel_evidence import render_source_figure_review_crops
from microgen_offline_vosk_capture import validate_vosk_words
from microgen_source_safe_orchestrator import atomic_json,digest,read_json,verify_workspace


class SemanticPacketError(ValueError):
    pass


_SKIP={"about","which","their","there","where","would","could","these",
       "those","because","function","value","values","point","since",
       "continuous","equation","formula","limit","approaches"}


def _source_terms(s):
    return {x.lower() for x in re.findall(r"[A-Za-z]{5,}",s)
            if x.lower() not in _SKIP}


def _context_only_anchors(text,words):
    """Two high-confidence, unique words within three seconds, for triage."""
    wanted=_source_terms(text)
    if len(wanted)<2:return []
    count=collections.Counter(w["word"].lower() for w in words)
    candidates=[w for w in words if w["word"].lower() in wanted
                and count[w["word"].lower()]==1 and w["conf"]>=.90]
    spans=[]
    for i,one in enumerate(candidates):
        for two in candidates[i+1:]:
            if (one["word"]!=two["word"] and 0<two["start"]-one["start"]<=3):
                spans.append({"context_words":[one["word"],two["word"]],
                              "local_start":one["start"],"local_end":two["end"],
                              "NOT_semantic_alignment":True})
    return spans[:2] if len(spans)==1 else []


def _protected_destination(output,existing):
    p=Path(output).resolve(strict=False)
    if p.exists() or p.is_symlink() or any(
            p==item or p.is_relative_to(item) or item.is_relative_to(p)
            for item in existing):
        raise SemanticPacketError("Review output must be a new isolated directory")
    return p


def _check_evidence(stage,selection,shadow,asr,video_dir,pixel_dir):
    plan=build_slide_clock(stage,selection,shadow)
    base=plan["stage"]
    source=Path(plan["source"]["source_root"]).resolve(strict=True)
    cuefile=base/"cues.json"
    if cuefile.is_symlink() or not cuefile.is_file():
        raise SemanticPacketError("Fresh corrected source-bound cues required")
    cues=read_json(cuefile)
    validate_audio_bound_cues(base,cues)
    if (cues.get("derivation")!="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH"
            or cues.get("publication_allowed") is not False
            or cues.get("spoken_word_alignment_verified") is not False
            or cues.get("mathematics_semantics_verified") is not False):
        raise SemanticPacketError("Old/approved cue manifest is not review evidence")
    asrfile=Path(asr).resolve(strict=True)
    if asrfile.is_symlink() or not asrfile.is_file():
        raise SemanticPacketError("Fresh current WAV ASR observations required")
    report=read_json(asrfile)
    audio_bindings=cues["audio_bindings"]
    if (report.get("status")!="CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH"
            or report.get("stage_audio_bindings")!=audio_bindings
            or report.get("source_pdf_sha256")!=plan["source"]["source_pdf_sha256"]
            or report.get("narration_sha256")!=plan["source"]["narration_sha256"]
            or report.get("publication_allowed") is not False
            or report.get("phonetic_identity_verified") is not False
            or report.get("semantic_alignment_verified") is not False
            or not isinstance(report.get("results"),list)
            or len(report["results"])!=17):
        raise SemanticPacketError("Stale ASR/model or invalid source lineage")
    words=[]
    for i,(entry,binding) in enumerate(zip(report["results"],audio_bindings),1):
        if (entry.get("slide")!=i
                or entry.get("source_wav_sha256")!=binding["wav_sha256"]
                or entry.get("phonetic_identity_verified") is not False
                or entry.get("semantic_word_alignment_certified") is not False):
            raise SemanticPacketError("Slide ASR identity or approval was forged")
        words.append(validate_vosk_words(
            entry.get("words"),limit_seconds=binding["duration_seconds"]))
    vidroot=Path(video_dir).resolve(strict=True)
    pxroot=Path(pixel_dir).resolve(strict=True)
    video=vidroot/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4"
    v=read_json(vidroot/"word_highlight_candidate_receipt.json")
    pix=read_json(pxroot/"word_pixel_audit_receipt.json")
    if (video.is_symlink() or not video.is_file()
            or v.get("status")!="ASR_WORD_HIGHLIGHT_TECHNICAL_CANDIDATE_NOT_APPROVED"
            or v.get("publication_allowed") is not False
            or v.get("video_sha256")!=digest(video)
            or v.get("source_pdf_sha256")!=plan["source"]["source_pdf_sha256"]
            or v.get("recognition_report_sha256")!=digest(asrfile)
            or v.get("cue_manifest_sha256")!=digest(cuefile)
            or v.get("corrected_pcm_sha256")!=plan["pcm"]["pcm_sha256"]
            or pix.get("status")!="CURRENT_ASR_OVERLAY_PIXEL_AUDIT_TECHNICAL_PASS"
            or pix.get("actual_overlay_pixels_verified") is not True
            or pix.get("publication_allowed") is not False
            or pix.get("video_sha256")!=digest(video)
            or pix.get("cues_sha256")!=digest(cuefile)
            or pix.get("asr_sha256")!=digest(asrfile)
            or pix.get("corrected_pcm_sha256")!=plan["pcm"]["pcm_sha256"]
            or pix.get("expected_cues")!=len(cues["elements"])
            or pix.get("positive_samples")!=len(cues["elements"])
            or pix.get("failed_samples")!=0
            or pix.get("post_cue_control_samples",0)<1):
        raise SemanticPacketError("Independent actual MP4 cue pixel evidence missing")
    script=read_json(source/"script_tts.json").get("slides")
    if not isinstance(script,list) or len(script)!=17:
        raise SemanticPacketError("Expected exact source narration for all slides")
    return plan,source,cues,report,words,script,video,pix


def build_corrected_semantic_review_packet(
        stage,selection,shadow,asr,video_dir,pixel_dir,output):
    plan,source,cues,report,words,script,video,pix=_check_evidence(
        stage,selection,shadow,asr,video_dir,pixel_dir)
    base=plan["stage"]
    asrfile=Path(asr).resolve(strict=True)
    cuefile=base/"cues.json"
    source_pdf=source/"slides.pdf"
    protected=(source,base,Path(selection).resolve(strict=True),
               Path(shadow).resolve(strict=True),
               asrfile.parent,Path(video_dir).resolve(strict=True),
               Path(pixel_dir).resolve(strict=True))
    dest=_protected_destination(output,protected)
    before={"pdf":digest(source_pdf),"script":digest(source/"script_tts.json"),
            "asr":digest(asrfile),"cues":digest(cuefile),"movie":digest(video)}
    dest.mkdir(parents=True,exist_ok=False)
    try:
        math_path=dest/"math_geometry.json"
        fig_path=dest/"figure_geometry.json"
        equation_region_inventory(source_pdf,math_path)
        figure_region_inventory(source_pdf,fig_path)
        math_doc=read_json(math_path)
        fig_doc=read_json(fig_path)
        if (math_doc.get("source_pdf_sha256")!=before["pdf"]
                or fig_doc.get("source_pdf_sha256")!=before["pdf"]
                or len(math_doc.get("slides",[]))!=17
                or len(fig_doc.get("slides",[]))!=17
                or math_doc.get("publication_allowed") is not False
                or fig_doc.get("publication_allowed") is not False):
            raise SemanticPacketError("Source-based mathematical/figure inventory drift")
        crops=dest/"figure_crops"
        render_source_figure_review_crops(source_pdf,fig_path,crops)
        fig_pixels=read_json(crops/"pixel_review_manifest.json")
        if (fig_pixels.get("source_pdf_sha256")!=before["pdf"]
                or fig_pixels.get("publication_allowed") is not False
                or fig_pixels.get("figure_region_count")!=fig_doc["figure_candidates"]):
            raise SemanticPacketError("Figure source pixel crop inventory mismatched")
        (dest/"audio").mkdir()
        (dest/"slides").mkdir()
        (dest/"math_regions").mkdir()
        qa=[]
        html_blocks=[]
        items=[]
        math_count=0
        heuristic=0
        with fitz.open(source_pdf) as pdf:
            if pdf.page_count!=17:
                raise SemanticPacketError("Original PDF unexpectedly incomplete")
            for i,page in enumerate(pdf,1):
                stagewav=base/"audio"/f"slide{i}.wav"
                if (stagewav.is_symlink() or
                        digest(stagewav)!=cues["audio_bindings"][i-1]["wav_sha256"]):
                    raise SemanticPacketError("Staged corrected WAV mutated")
                copied=dest/"audio"/f"slide{i:02d}_CORRECTED_UNREVIEWED.wav"
                shutil.copyfile(stagewav,copied)
                if digest(copied)!=digest(stagewav):
                    raise SemanticPacketError("Review audio copy differs")
                jpg=dest/"slides"/f"slide{i:02d}.png"
                page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).save(jpg)
                math_items=[]
                for j,region in enumerate(math_doc["slides"][i-1]["regions"],1):
                    rect=fitz.Rect(region["bbox"]) & page.rect
                    if (rect.is_empty or not page.rect.contains(rect)
                            or j>60):
                        raise SemanticPacketError("Invalid math geometry")
                    clip=rect+(-4,-4,4,4)
                    clip=clip & page.rect
                    png=f"math_regions/slide{i:02d}_math{j:02d}.png"
                    page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),
                                    clip=clip,alpha=False).save(dest/png)
                    anchors=_context_only_anchors(region["line_text"],words[i-1])
                    heuristic+=bool(anchors)
                    rec={"id":f"M-{i:02d}-{j:02d}","slide":i,"kind":"math",
                         "source_text":region["line_text"],"pdf_box":region["bbox"],
                         "image":png,"candidate_asr_context_only":anchors,
                         "semantic_alignment_verified":False}
                    math_items.append(rec)
                    qa.append([rec["id"],i,"math","UNREVIEWED","UNREVIEWED",""])
                figures=[]
                for j,fig in enumerate(fig_doc["slides"][i-1]["figure_geometry_candidates"],1):
                    png=f"figure_crops/slide{i:02d}_region{j:02d}.png"
                    file=dest/png
                    if not file.is_file():
                        raise SemanticPacketError("Missing figure source PDF crop")
                    figures.append({"id":f"F-{i:02d}-{j:02d}","slide":i,
                                    "kind":fig["kind"],"pdf_box":fig["box"],
                                    "image":png,"image_sha256":digest(file),
                                    "caption_to_spoken_figure_verified":False})
                    qa.append([figures[-1]["id"],i,"figure","UNREVIEWED","UNREVIEWED",""])
                asr_items=words[i-1]
                text=script[i-1].get("tts_text") or script[i-1].get("narration")
                if not isinstance(text,str) or not text.strip():
                    raise SemanticPacketError("Narration missing for a source slide")
                record={"slide":i,"source_page_png":f"slides/slide{i:02d}.png",
                        "corrected_wav":f"audio/slide{i:02d}_CORRECTED_UNREVIEWED.wav",
                        "corrected_wav_sha256":digest(copied),
                        "source_narration":text,"asr_observations":asr_items,
                        "math_candidates":math_items,
                        "figure_candidates":figures,
                        "semantic_QA_approved":False}
                items.append(record)
                cards=[]
                for row in math_items:
                    candidates=row["candidate_asr_context_only"]
                    detail=((", contextual ASR at "+str(candidates[0]["local_start"])+" s")
                            if candidates else ", no unique ASR phrase anchor")
                    cards.append('<figure><img loading="lazy" src="'+row["image"]+'"/>'
                                 '<figcaption>'+html.escape(row["id"])+": "+
                                 html.escape(row["source_text"][:130])+
                                 html.escape(detail)+" — UNREVIEWED</figcaption></figure>")
                for row in figures:
                    cards.append('<figure><img loading="lazy" src="'+row["image"]+'"/>'
                                 '<figcaption>'+html.escape(row["id"])+
                                 " — possible PDF raster/vector figure; UNREVIEWED</figcaption></figure>")
                spoken=" ".join(f'{w["word"]} [{w["start"]:.2f}]' for w in asr_items)
                html_blocks.append(
                    f'<section><h2>Slide {i} — {len(math_items)} mathematical and {len(figures)} figure candidates</h2>'
                    f'<img class="slide" src="{record["source_page_png"]}" alt="Original PDF slide {i}"/>'
                    f'<audio controls preload="none" src="{record["corrected_wav"]}"></audio>'
                    f'<details><summary>Exact source narration</summary><p>{html.escape(text)}</p></details>'
                    f'<details><summary>Timestamped Vosk hypothesis (NOT ground truth)</summary><p>{html.escape(spoken)}</p></details>'
                    +''.join(cards)+'</section>')
                math_count+=len(math_items)
        if (math_count!=math_doc["candidate_regions"] or
                sum(len(x["figure_candidates"]) for x in items)!=fig_doc["figure_candidates"]):
            raise SemanticPacketError("Lost a math or figure candidate")
        with (dest/"manual_semantic_review.csv").open("w",encoding="utf-8",newline="") as handle:
            writer=csv.writer(handle)
            writer.writerow(["source_region_id","slide","region_kind",
                             "spoken_correspondence","academic_correctness","reviewer_note"])
            writer.writerows(qa)
        stylesheet=(
            "<style>body{font:16px system-ui,sans-serif;max-width:950px;margin:2rem auto;"
            "line-height:1.5}section{margin:2rem 0;border:1px solid #aaa;padding:1rem}"
            "img{max-width:100%;display:block}img.slide{width:100%}"
            "audio{width:100%}figure{border-left:3px solid #aaa;padding:.5rem;margin:.5rem 0}"
            "figcaption{font-size:.9rem}details{margin:.8rem 0}</style>")
        index=('<!doctype html><html lang="en"><meta charset="UTF-8"/>'
               '<title>Corrected Section 2.5 — semantic review ONLY</title>'
               +stylesheet+'<h1>Thomas Calculus 2.5: mathematics/figure/spoken review</h1>'
               '<p>These are PDF geometry and ASR observations only. Every item '
               'is UNREVIEWED. 66 word overlays passed pixel QA, but their '
               'mathematical meaning, figure association, c/y pronunciation, '
               'speaker identity and publication are NOT certified.</p>'
               +''.join(html_blocks)+'</html>')
        (dest/"index.html").write_text(index,encoding="utf8")
        now={"pdf":digest(source_pdf),"script":digest(source/"script_tts.json"),
             "asr":digest(asrfile),"cues":digest(cuefile),"movie":digest(video)}
        if now!=before or verify_workspace(base)!=plan["source"]:
            raise SemanticPacketError("Source/ASR/video changed during review creation")
        metadata={"schema_version":1,
                  "status":"CORRECTED_MATH_FIGURE_SOURCE_BOUND_REVIEW_UNAPPROVED",
                  "source_pdf_sha256":before["pdf"],
                  "narration_sha256":before["script"],
                  "corrected_asr_sha256":before["asr"],
                  "current_cues_sha256":before["cues"],
                  "corrected_video_sha256":before["movie"],
                  "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
                  "word_overlay_pixel_receipt_sha256":digest(Path(pixel_dir)/"word_pixel_audit_receipt.json"),
                  "slide_count":17,"corrected_audio_slides":17,
                  "math_region_candidates":math_count,
                  "figure_region_candidates":fig_doc["figure_candidates"],
                  "math_candidates_with_text_context_only":heuristic,
                  "unreviewed_region_decisions":len(qa),
                  "slides":items,"all_mathematical_semantics_verified":False,
                  "all_figure_spoken_correspondence_verified":False,
                  "pronunciation_approved":False,
                  "speaker_identity_approved":False,
                  "publication_allowed":False}
        atomic_json(dest/"semantic_review_receipt.json",metadata)
        return {"slides":17,"math_candidates":math_count,
                "figure_candidates":fig_doc["figure_candidates"],
                "contextual_math_hints":heuristic,"unreviewed":len(qa),
                "html":str(dest/"index.html"),
                "publication_allowed":False}
    except Exception:
        shutil.rmtree(dest)
        raise
