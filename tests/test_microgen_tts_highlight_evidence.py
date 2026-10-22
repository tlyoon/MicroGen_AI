import hashlib,io,json
import pytest
import microgen_tts_highlight_evidence as h

def example_manifest():
    return {"schema_version": 1, "video_sha256": "a"*64, "cues": [
        {"cue_id":"cue1","slide_number":1,"element_id":"eq1","narration_id":"sentence1",
         "start_seconds":1.0,"end_seconds":2.0,"box":[0,0,2,2],"slide_image_sha256":"b"*64}]}

def test_manifest_contract_and_false_publication_flag():
    m = example_manifest()
    assert h.validate_manifest(m)["cue_count"] == 1
    assert h.validate_manifest(m)["ready_for_publication"] is False
    for key, invalid in [("video_sha256","abc"),("schema_version",True),("cues",[])]:
        bad = dict(m, **{key:invalid})
        with pytest.raises(h.HighlightEvidenceError):
            h.validate_manifest(bad)

def test_manifest_duplicate_and_bad_geometry():
    m=example_manifest();m["cues"].append(dict(m["cues"][0]))
    with pytest.raises(h.HighlightEvidenceError): h.validate_manifest(m)
    m["cues"]=m["cues"][:1];m["cues"][0]["box"]=[0,0,0,2]
    with pytest.raises(h.HighlightEvidenceError):h.validate_manifest(m)
