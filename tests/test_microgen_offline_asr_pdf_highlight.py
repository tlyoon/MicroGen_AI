"""ASR text/PDF geometry must be uniquely matched; all status remains QA only."""
import json
import wave
import pymupdf as fitz
import pytest
from microgen_source_safe_orchestrator import digest
from microgen_offline_asr_pdf_highlight import HighlightPilotError,propose_unique_word_cues

def _wav(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(bytes(32000))

def _json(path,thing):
    path.write_text(json.dumps(thing),encoding="utf8")

def fixture(tmp_path):
    pdf=tmp_path/"pages.pdf"
    with fitz.open() as doc:
        for i in range(5):
            pg=doc.new_page(width=640,height=360)
            if i==4:pg.insert_text((35,50),"formal continuity about mathematical limits",fontsize=18)
        doc.save(pdf)
    root=tmp_path/"bundle"
    old=root/"original_scene_references"/"slide05_reference.wav"
    new=root/"unapproved_trials"/"slide05_CDOT_UNREVIEWED.wav"
    _wav(old);_wav(new)
    manifest={"status":"TECHNICAL_PRONUNCIATION_REVIEW_READY_NOT_APPROVED",
       "publication_allowed":False,"source_slide_pdf_sha256":digest(pdf),
       "narration_sha256":"n"*64,"source_mp4_sha256":"m"*64,
       "slides_to_review":[5],
       "historical_audio_candidates":[{"slide":5,"risk_class":"CDOT",
        "wav_sha256":digest(new),"phonetic_approved":False,
        "publication_allowed":False,"source_media_receipt_bound":True}]}
    _json(root/"review_manifest.json",manifest)
    def word(name,start):
        return {"word":name,"start":start,"end":start+.18,"conf":.99}
    data={"model":"offline_fake","publication_allowed":False,
       "model_word_timestamps_not_ground_truth":True,
       "results":[
           {"file":old.name,"source_wav_sha256":digest(old),
            "words":[],"phonetic_identity_verified":False,
            "semantic_word_alignment_certified":False},
           {"file":new.name,"source_wav_sha256":digest(new),
            "words":[word("formal",.1),word("continuity",.5)],
            "phonetic_identity_verified":False,
            "semantic_word_alignment_certified":False}]}
    report=tmp_path/"asr.json";_json(report,data)
    return root,report,pdf

def test_proposes_only_unique_high_confidence_pdf_words(tmp_path):
    root,report,pdf=fixture(tmp_path)
    result=propose_unique_word_cues(root,report,pdf,5,"CDOT")
    assert [x["text"] for x in result["cues"]]==["formal","continuity"]
    assert all(x["source_word_unique_in_pdf"] for x in result["cues"])
    assert not result["math_equation_alignment_verified"]
    assert not result["publication_allowed"]

def test_original_pdf_mutation_invalidates_asr_geometry(tmp_path):
    root,report,pdf=fixture(tmp_path)
    with pdf.open("ab") as f:f.write(b"edited")
    with pytest.raises(HighlightPilotError):
        propose_unique_word_cues(root,report,pdf,5,"CDOT")

def test_repeated_asr_word_is_not_assigned_single_pdf_box(tmp_path):
    root,report,pdf=fixture(tmp_path)
    j=json.loads(report.read_text())
    j["results"][1]["words"]=[{"word":"formal","start":.1,"end":.3,"conf":1.},
                               {"word":"formal","start":.4,"end":.6,"conf":1.},
                               {"word":"continuity","start":.7,"end":.9,"conf":1.}]
    _json(report,j)
    result=propose_unique_word_cues(root,report,pdf,5,"CDOT")
    assert [x["text"] for x in result["cues"]]==["continuity"]

def test_unseen_or_invalid_slide_will_not_generate_guess(tmp_path):
    root,report,pdf=fixture(tmp_path)
    with pytest.raises(HighlightPilotError):
        propose_unique_word_cues(root,report,pdf,3,"CDOT")
