"""Evidence tests for complete offline neural MP4 source and voice chain."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_teaching_slide_render import render_teaching_candidate
from microgen_offline_neural_candidate_video import check_candidate_video_inputs,NeuralVideoError
from test_microgen_source_teaching_slide_render import prepare

def fixture(root):
    stage,n,plan=prepare(root)
    r=json.loads(n.read_text())
    requests=[]
    for i,row in enumerate(r["slides"],1):
        speech=f"Source grounded lecture paragraph number {i} is spoken."
        h=hashlib.sha256(speech.encode()).hexdigest()
        row["spoken_text_sha256"]=h
        requests.append({"slide":i,"input_text":speech,"text_sha256":h,
            "source_pdf_sha256":r["source_pdf_sha256"],"teaching_pdf_sha256":None})
    n.write_text(json.dumps(r))
    slides=root/"slides"
    render_teaching_candidate(stage,n,plan,slides)
    slide_pdf=slides/"slides_teaching_candidate.pdf"
    sh=sha_file(slide_pdf)
    for row in requests: row["teaching_pdf_sha256"]=sh
    formal=root/"handoff.json"
    formal.write_text(json.dumps({"formal_voice_provider":None,"formal_voice_name":None,
        "formal_production_ready":False,"publication_allowed":False,
        "slide_count":8,"requests":requests}))
    audio=root/"wav";audio.mkdir()
    rows=[]
    for i,req in enumerate(requests,1):
        path=audio/f"slide{i:02d}.wav"
        path.write_bytes(b"sample-file-"+bytes([i]))
        rows.append({"slide":i,"text_sha256":req["text_sha256"],
            "source_pdf_sha256":r["source_pdf_sha256"],
            "teaching_pdf_sha256":sh,
            "wav_filename":path.name,
            "probe_wav_sha256":sha_file(path),"seconds":30.0,
            "local_candidate_not_formal":True,
            "pronunciation_acoustically_verified":False})
    (audio/"candidate_audio_receipt.json").write_text(json.dumps({
        "status":"EIGHT_OFFLINE_NEURAL_WAV_CANDIDATES_NOT_FORMAL",
        "formal_handoff_sha256":sha_file(formal),
        "formal_voice_authorized":False,"publication_allowed":False,
        "slide_count":8,"slides":rows,"total_duration_seconds":240,
        "model_name":"en_US-ljspeech-medium","model_sha256":"a"*64}))
    return slides,n,formal,audio

class VideoCandidateTests(unittest.TestCase):
    def test_8_source_bound_wavs_match_narrated_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            s,n,h,a=fixture(Path(td))
            z=check_candidate_video_inputs(s,n,h,a)
            self.assertEqual(z["slide_count"],8)
            self.assertEqual(z["total_audio_seconds"],240)
            self.assertFalse(z["publication_allowed"])
            self.assertFalse(z["formal_voice_authorized"])

    def test_swapped_or_modified_wav_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s,n,h,a=fixture(Path(td))
            (a/"slide06.wav").write_bytes(b"swapped")
            with self.assertRaises(NeuralVideoError):
                check_candidate_video_inputs(s,n,h,a)

    def test_false_formal_voice_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s,n,h,a=fixture(Path(td))
            meta=json.loads(h.read_text());meta["formal_voice_name"]="en_US-ljspeech-medium"
            h.write_text(json.dumps(meta))
            with self.assertRaises(NeuralVideoError):
                check_candidate_video_inputs(s,n,h,a)

    def test_source_text_identity_failure_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s,n,h,a=fixture(Path(td))
            meta=json.loads(h.read_text());meta["requests"][4]["input_text"]="changed source words"
            h.write_text(json.dumps(meta))
            receipt=a/"candidate_audio_receipt.json";x=json.loads(receipt.read_text())
            x["formal_handoff_sha256"]=sha_file(h)
            receipt.write_text(json.dumps(x))
            with self.assertRaises(NeuralVideoError):
                check_candidate_video_inputs(s,n,h,a)

if __name__=="__main__":unittest.main()
