import hashlib,json,pytest
import microgen_tts_pronunciation_groundtruth as g

def event():
    return {"event_id":"event_1","cue_id":"cue1","expected_phrase":"c.","heard_phrase":"c dot",
      "verdict":"CORRECT","start_seconds":1.0,"window_seconds":.2,
      "pcm_sha256":"a"*64,"reviewer_id":"R1"}

def manifest():
    return {"schema_version":1,"video_sha256":"d"*64,"cues":[{"cue_id":"cue1",
      "slide_number":1,"element_id":"math1","narration_id":"narration1",
      "start_seconds":1.0,"end_seconds":2.0,"box":[0,0,2,2],
      "slide_image_sha256":"b"*64}]}

def test_pcm_witness_fingerprint_guard(tmp_path,monkeypatch):
    p=tmp_path/"clip.mp4";p.write_bytes(b"media")
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(g,"extract_pcm_window",lambda *args,**kwargs:b"\0"*6400)
    w=g.witness_pcm(p,sha,1.0,.2,duration_seconds=4)
    assert w["sample_count"]==3200 and not w["pronunciation_verified"]
    p.write_bytes(b"mutated")
    with pytest.raises(g.AnnotationError):g.witness_pcm(p,sha,1.0,.2,duration_seconds=4)

def test_review_event_rejects_unbounded_and_untrusted_fields():
    e=event()
    assert not g.validate_event(e)["independent_acoustic_truth_verified"]
    for k,v in [("window_seconds",12),("start_seconds",float("nan")),
      ("verdict","APPROVED"),("expected_phrase",""),("reviewer_id","x!*"),
      ("pcm_sha256","wrong"),("heard_phrase","circa\nx")]:
        bad={**e,k:v}
        with pytest.raises(g.AnnotationError):g.validate_event(bad)
    with pytest.raises(g.AnnotationError):g.validate_event({**e,"reviewer_authenticated":True})

def test_review_clip_refuses_forged_hash(tmp_path,monkeypatch):
    p=tmp_path/"test.mp4";p.write_bytes(b"movie")
    vid=hashlib.sha256(p.read_bytes()).hexdigest()
    e=event()
    monkeypatch.setattr(g,"witness_pcm",lambda *args,**kw:{"pcm_sha256":"b"*64})
    with pytest.raises(g.AnnotationError):g.verify_label_clip(p,vid,e,duration_seconds=5)
    monkeypatch.setattr(g,"witness_pcm",lambda *args,**kw:{"pcm_sha256":e["pcm_sha256"]})
    assert not g.verify_label_clip(p,vid,e,duration_seconds=5)["phonetic_label_verified"]

def test_packet_requires_same_clip_and_unique_observers():
    e=event();copy={**e,"reviewer_id":"R2","verdict":"DEFECT","heard_phrase":"circa"}
    packet={"schema_version":1,"video_sha256":"d"*64,"observations":[e,copy]}
    assert g.validate_review_packet(packet)["event_count"]==1
    with pytest.raises(g.AnnotationError):
        g.validate_review_packet({**packet,"observations":[e,e]})
    with pytest.raises(g.AnnotationError):
        g.validate_review_packet({**packet,"observations":[e,{**copy,"start_seconds":1.1}]})
