import io,json,math,wave,struct
from pathlib import Path
import pytest
import pymupdf as fitz
import microgen_production_bridge as b

def write_lesson(root):
    with fitz.open() as doc:
        for i in range(2):
            p=doc.new_page(width=640,height=360)
            p.insert_text((36,52),"limit as x approaches c.",fontsize=18)
        doc.save(root/"slides.pdf")
    (root/"script_tts.json").write_text(json.dumps({"slides":[
       {"slide":1,"tts_text":"Take the limit at c."},
       {"slide":2,"tts_text":"Evaluate at c."}]}),encoding="utf8")
def write_wav(path,seconds):
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(b"\0\0"*int(seconds*16000))

def test_readonly_inventory_matches_actual_pdf_pages(tmp_path):
    write_lesson(tmp_path)
    assert b.inspect_lesson(tmp_path)["page_count"]==2
    assert not b.inspect_lesson(tmp_path)["complete_audio_set"]
    obj=json.loads((tmp_path/"script_tts.json").read_text())
    obj["slides"][1]["slide"]=3
    (tmp_path/"script_tts.json").write_text(json.dumps(obj))
    with pytest.raises(b.BridgeError):b.inspect_lesson(tmp_path)

def test_actual_wav_timeline_is_monotone(tmp_path):
    write_lesson(tmp_path)
    for i in (1,2):write_wav(tmp_path/f"slide{i}.wav",.4)
    report=b.measured_wav_timeline(tmp_path,2)
    assert report["duration_seconds"]==pytest.approx(.8)
    assert report["slide_intervals"][1]["start_seconds"]==pytest.approx(.4)
    assert report["individual_word_times_verified"] is False
    (tmp_path/"slide2.wav").unlink()
    with pytest.raises(b.BridgeError):b.measured_wav_timeline(tmp_path,2)

def test_pdf_element_inventory_real_fitzz(tmp_path):
    write_lesson(tmp_path)
    rows=b.pdf_element_inventory(tmp_path/"slides.pdf")
    assert len(rows)==2 and "limit" in [x["text"] for x in rows[0]["words"]]
    assert rows[0]["source_geometry_extracted"]

def test_highlight_cues_require_exact_pdf_word_and_wav_bounds(tmp_path):
    write_lesson(tmp_path)
    for i in (1,2):write_wav(tmp_path/f"slide{i}.wav",.4)
    pages=b.pdf_element_inventory(tmp_path/"slides.pdf")
    timing=b.measured_wav_timeline(tmp_path,2)
    word=next(w for w in pages[0]["words"] if w["text"]=="limit")
    cue={"slide":1,"text":"limit","box":word["box"],"start_seconds":.1,"end_seconds":.3}
    assert b.validate_highlight_cues([cue],pages,timing)["cue_geometry_validated"]
    with pytest.raises(b.BridgeError):
        b.validate_highlight_cues([{**cue,"text":"fabricated"}],pages,timing)
