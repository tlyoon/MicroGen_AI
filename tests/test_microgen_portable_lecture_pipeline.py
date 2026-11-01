"""End-to-end portable PDF/media contract tests use only synthetic sections."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_slide_render import (
    render_portable_slides,PortableSlideError)
from microgen_portable_lecture_pipeline import (
    run_portable_pipeline,PortablePipelineError)
from microgen_offline_diagnostic_av import inspect_inputs
from test_microgen_portable_section_contract import create

def setup(root,with_figure=False):
    stage=root/"source";stage.mkdir()
    source,narration,plan,contract=create(stage)
    # A complete media pipeline must explicitly declare nonformal narration.
    # The earlier academic-only contract deliberately did not require this.
    n=json.loads(narration.read_text())
    n["formal_voice_authorized"]=False
    narration.write_text(json.dumps(n))
    m=json.loads(contract.read_text())
    m["narration_sha256"]=sha_file(narration)
    contract.write_text(json.dumps(m))
    if with_figure:
        img=stage/"triangle.png"
        Image.new("RGB",(80,90),(75,150,210)).save(img)
        x=json.loads(contract.read_text())
        x["figures"]=[{"slide":3,"filename":"triangle.png","sha256":sha_file(img),
            "caption":"Synthetic original triangle image"}]
        contract.write_text(json.dumps(x))
    model=root/"model";model.mkdir()
    (model/"en_US-ljspeech-medium.onnx").write_bytes(b"M"*20000)
    (model/"en_US-ljspeech-medium.onnx.json").write_text(json.dumps({
        "audio":{"sample_rate":22050},"num_speakers":1,
        "language":{"code":"en_US"}}))
    (model/"MODEL_CARD").write_text(
        "Model card for ljspeech, US English female voice; "
        "License: public domain; trained from scratch")
    vosk=root/"vosk";(vosk/"am").mkdir(parents=True)
    interpreter=Path(sys.executable).resolve(strict=True)
    return stage,narration,plan,contract,model,interpreter,vosk,interpreter

class PortableLectureTests(unittest.TestCase):
    def test_source_to_three_slide_pdf_without_serway_special_cases(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root)
            output=root/"pdf"
            record=render_portable_slides(*a[:4],output)
            self.assertEqual(record["section_id"],"B.2")
            self.assertEqual(record["slide_count"],3)
            self.assertFalse(record["publication_allowed"])
            self.assertFalse(record["complete_academic_correctness_proven"])
            with fitz.open(output/"slides_teaching_candidate.pdf") as pages:
                self.assertEqual(len(pages),3)
                self.assertTrue(all("B.2" in p.get_text() for p in pages))

    def test_figure_source_pixel_identity_and_chapter_label(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root,with_figure=True)
            out=root/"pdf"
            result=render_portable_slides(*a[:4],out)
            self.assertTrue(result["figures_exact_original_pixels_verified"])
            with fitz.open(out/"slides_teaching_candidate.pdf") as pages:
                self.assertEqual(len(pages[2].get_images()),1)
            self.assertEqual(result["slides"][2]["figure"]["filename"],"triangle.png")

    def test_missing_formal_voice_restriction_rejected_at_render_boundary(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root)
            n=json.loads(a[1].read_text())
            n.pop("formal_voice_authorized")
            a[1].write_text(json.dumps(n))
            m=json.loads(a[3].read_text())
            m["narration_sha256"]=sha_file(a[1])
            a[3].write_text(json.dumps(m))
            with self.assertRaises(PortableSlideError):
                render_portable_slides(*a[:4],root/"denied")

    def test_figure_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root,with_figure=True)
            m=json.loads(a[3].read_text())
            m["figures"][0]["filename"]="../outside.png"
            a[3].write_text(json.dumps(m))
            with self.assertRaises(PortableSlideError):
                render_portable_slides(*a[:4],root/"denied")

    def test_corrupted_figure_sha_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root,with_figure=True)
            image=a[0]/"triangle.png"
            image.write_bytes(b"changed source asset")
            with self.assertRaises(PortableSlideError):
                render_portable_slides(*a[:4],root/"bad")

    def test_adversarial_academic_contract_fails_before_render(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root)
            m=json.loads(a[3].read_text())
            m["next_section_marker"]="missing next section"
            a[3].write_text(json.dumps(m))
            with self.assertRaises(Exception):
                render_portable_slides(*a[:4],root/"bad")

    def test_mocked_local_stages_commit_transaction_without_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root,with_figure=True)
            def synth(narration,slides,contract,model,python,folder):
                folder.mkdir()
                (folder/"portable_audio_receipt.json").write_text('{"test":true}')
                return {"total_seconds":75.0}
            def asr(folder,narration,contract,vosk,ffmpeg,out):
                out.write_text('{"test":true}')
                return {"targeted_pronunciation_risks":0}
            def mux(slides,narration,wavs,dest,**kwargs):
                dest.mkdir()
                (dest/"lecture_diagnostic_only.mp4").write_bytes(b"synthetic fixture not real MP4")
                (dest/"diagnostic_av_receipt.json").write_text('{"test":true}')
                return {"slide_count":3,"status":"DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION",
                    "all_slide_midpoints_source_pixel_checked":True,
                    "video_slide_frame_alignment":[{"slide":i,"mean_absolute_rgb_fraction":0.001}
                               for i in range(1,4)],
                    "diagnostic_mp4_sha256":sha_file(dest/"lecture_diagnostic_only.mp4"),
                    "diagnostic_mp4_duration_seconds":75.6,
                    "publication_allowed":False}
            target=root/"completed"
            with patch("microgen_portable_lecture_pipeline.synthesize_portable",side_effect=synth),\
                 patch("microgen_portable_lecture_pipeline.observe_portable_asr",side_effect=asr),\
                 patch("microgen_portable_lecture_pipeline.build_demo_video",side_effect=mux):
                r=run_portable_pipeline(*a,target)
            self.assertEqual(r["section_id"],"B.2")
            self.assertEqual(r["slide_count"],3)
            self.assertFalse(r["publication_allowed"])
            self.assertTrue((target/"portable_pipeline_receipt.json").is_file())
            self.assertTrue((target/"video"/"lecture_portable_neural_candidate.mp4").is_file())
            self.assertTrue((target/"independent_portable_academic_coverage.json").is_file())
            self.assertFalse((target/"temporary_mux").exists())
            self.assertFalse(r["fully_general_academic_synthesis_proven"])
            self.assertEqual(len(list(root.glob(".microgen-portable-campaign-*"))),0)

    def test_synthesis_failure_rolls_back_output_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root)
            original=sha_file(a[0]/"source.pdf")
            def fail(*args,**kwargs):raise RuntimeError("offline model failed")
            with patch("microgen_portable_lecture_pipeline.synthesize_portable",side_effect=fail):
                with self.assertRaises(RuntimeError):
                    run_portable_pipeline(*a,root/"failed")
            self.assertFalse((root/"failed").exists())
            self.assertEqual(original,sha_file(a[0]/"source.pdf"))
            self.assertEqual(len(list(root.glob(".microgen-portable-campaign-*"))),0)

    def test_duplicate_destination_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);a=setup(root)
            target=root/"existing";target.mkdir()
            with self.assertRaises(PortablePipelineError):
                run_portable_pipeline(*a,target)

if __name__=="__main__":unittest.main()
