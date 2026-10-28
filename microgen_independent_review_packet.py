"""Source-bound per-slide academic/listening QA review packet.

Review pages and links are evidence for a reviewer, never independent
human sign-off, voice authentication or mathematical approval.
"""
from pathlib import Path
import pymupdf as fitz
from microgen_source_safe_orchestrator import (
    verify_workspace,read_json,digest,atomic_json,OrchestratorError
)

class IndependentPacketError(OrchestratorError):
    pass

def prepare_full_lecture_review_packet(recovery,math_report,figure_report,
                                       figure_pixel_folder,defect_report,
                                       cue_report,shadow_folder,output):
    root=Path(recovery).resolve(strict=True)
    source_info=verify_workspace(root)
    source=Path(source_info["source_root"]).resolve(strict=True)
    math=read_json(math_report);figure=read_json(figure_report)
    defect=read_json(defect_report);cue=read_json(cue_report)
    shadow=read_json(Path(shadow_folder)/"shadow_receipt.json")
    pix=read_json(Path(figure_pixel_folder)/"pixel_review_manifest.json")
    dest=Path(output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or
        dest.is_relative_to(source) or dest.is_relative_to(root)):
        raise IndependentPacketError("Never overwrite original media/review stage")
    key=source_info["source_pdf_sha256"]
    if (any(x.get("source_pdf_sha256")!=key for x in (math,figure,pix)) or
        defect.get("narration_sha256")!=source_info["narration_sha256"] or
        cue.get("original_slide_pdf_sha256")!=key or
        shadow.get("publication_allowed") is not False or
        cue.get("publication_allowed") is not False or
        len(math.get("slides",[]))!=17 or len(figure.get("slides",[]))!=17):
        raise IndependentPacketError("Cross-stage source or QA provenance mismatch")
    pdf=source/"slides.pdf"
    if digest(pdf)!=key:raise IndependentPacketError("Original PDF source changed")
    dest.mkdir()
    items=[]
    with fitz.open(pdf) as pages:
        for i in range(1,18):
            pixmap=pages[i-1].get_pixmap(matrix=fitz.Matrix(1,1),
                                        colorspace=fitz.csRGB,alpha=False)
            screenshot=dest/f"source_slide_{i:02d}.png"
            pixmap.save(screenshot)
            defects=[x for x in defect["risks"] if x["slide"]==i]
            fig=[x for x in pix["regions"] if x["slide"]==i]
            equations=math["slides"][i-1]["regions"]
            anchor=cue["slides"][i-1]["cues"]
            rows=shadow.get("audio_segments",[])
            if len(rows)!=17 or rows[i-1]["slide"]!=i:
                raise IndependentPacketError("Shadow audio slide identity changed")
            items.append({"slide":i,"source_page_png":screenshot.name,
              "source_page_png_sha256":digest(screenshot),
              "math_line_candidates":len(equations),
              "figure_pixel_crops":[x["png_name"] for x in fig],
              "word_highlights_current_source_count":len(anchor),
              "pronunciation_risk_observations":defects,
              "shadow_audio_kind":rows[i-1]["source"],
              "listening_review_required":True,
              "mathematics_and_figures_review_required":True,
              "highlight_semantics_review_required":True,
              "speaker_consistency_approval_required":True,
              "release_approved":False})
    if digest(pdf)!=key:raise IndependentPacketError("Original PDF altered")
    metadata={"schema_version":1,"status":"REVIEW_PACKET_READY_NOT_RELEASE_READY",
      "source_pdf_sha256":key,"source_narration_sha256":source_info["narration_sha256"],
      "slides":items,"total_slides":17,
      "current_original_audio_candidate_mp4_source":str(source/"slides.mp4"),
      "shadow_pcm_sha256":shadow["shadow_sha256"],
      "all_academic_and_listening_checks_performed":False,
      "publication_allowed":False}
    atomic_json(dest/"review_index.json",metadata)
    return {"pages":17,"figure_crops_indexed":sum(len(x["figure_pixel_crops"]) for x in items),
            "risk_observations":sum(len(x["pronunciation_risk_observations"]) for x in items),
            "ready_for_publication":False,"review_dir":str(dest)}
