"""No-cloud offline lecturer handoff regression tests."""
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

import microgen_review_pack as review


class ReviewPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "8.4"
        self.source.mkdir()
        self.output = self.root / "review"

    def make_valid_fixture(self, duration=25.0):
        import pymupdf as fitz
        for name in ("source.pdf", "slides.pdf"):
            doc=fitz.open()
            page=doc.new_page()
            page.insert_text((50,50),"Fixture page")
            doc.save(self.source/name)
            doc.close()
        with wave.open(str(self.source/"slide1.wav"),"wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(8000)
            stream.writeframes(b"\0\0"*8000)
        (self.source/"slides.mp4").write_bytes(b"mock-media-copy-only")
        (self.source/"script_tts.json").write_text(json.dumps({
            "slides":[{"slide":1,"title":"<script>alert(9)</script>",
                       "narration":"Use <x> and tts explanation.",
                       "tts_text":"Use x and tts explanation."}]
        }),encoding="utf-8")
        receipt = {
            "slide_count":1,"wav_sha256":[review.quality.sha256(self.source/"slide1.wav")],
            "audio_seconds":1,"video_seconds":duration,
            "source_sha256":review.quality.sha256(self.source/"source.pdf"),
            "slides_pdf_sha256":review.quality.sha256(self.source/"slides.pdf"),
            "mp4_sha256":review.quality.sha256(self.source/"slides.mp4"),
            "unmapped_source_crops":[{"page":1,"name":"fig_1.png"}],
        }
        (self.source/".microgen_verified_completion.json").write_text(json.dumps(receipt))
        return receipt

    def test_unverified_bundle_refused(self):
        with self.assertRaisesRegex(review.ReviewPackError,"completion receipt"):
            review.build_pack(self.source,self.output)
        self.assertFalse(self.output.exists())

    def test_production_folder_output_refused(self):
        self.make_valid_fixture()
        with mock.patch.object(review.quality,"published_manifest_valid",return_value=True):
            with self.assertRaisesRegex(review.ReviewPackError,"inside source"):
                review.build_pack(self.source,self.source/"review")

    def test_overwrite_refused(self):
        self.make_valid_fixture()
        self.output.mkdir()
        with mock.patch.object(review.quality,"published_manifest_valid",return_value=True):
            with self.assertRaisesRegex(review.ReviewPackError,"Existing review folder"):
                review.build_pack(self.source,self.output)

    def test_complete_safe_offline_pack(self):
        receipt=self.make_valid_fixture(duration=601)
        original=sorted(p.name for p in self.source.iterdir())
        with mock.patch.object(review.quality,"published_manifest_valid",return_value=True):
            result=review.build_pack(self.source,self.output,edition="qa-candidate")
        self.assertEqual(result["status"],"NOT_REVIEWED")
        self.assertEqual(sorted(p.name for p in self.source.iterdir()),original)
        self.assertTrue((self.output/"media/slide1.wav").is_file())
        self.assertTrue((self.output/"previews/slide_001.png").is_file())
        self.assertTrue((self.output/"previews/source_001.png").is_file())
        self.assertEqual(review.quality.sha256(self.output/"media/slides.mp4"),
                         receipt["mp4_sha256"])
        page=(self.output/"index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(9)</script>",page)
        self.assertIn("&lt;script&gt;alert(9)&lt;/script&gt;",page)
        self.assertIn("exceeds ten minutes",page)
        self.assertIn("Export review JSON",page)
        info=json.loads((self.output/"review_inventory.json").read_text())
        self.assertEqual(info["approval"],"NOT_REVIEWED")
        self.assertEqual(info["slides"][0]["start_seconds"],0)
        hashes=json.loads((self.output/"review_pack_manifest.json").read_text())
        for name,digest in hashes["files_sha256"].items():
            self.assertEqual(review.quality.sha256(self.output/name),digest,name)
        self.assertIn("| 1 |", (self.output/"REVIEW_CHECKLIST.md").read_text())

    def test_source_drift_fails_without_publishing_review(self):
        self.make_valid_fixture()
        with mock.patch.object(review.quality,"published_manifest_valid",
                               side_effect=[True,False]):
            with self.assertRaisesRegex(review.ReviewPackError,"changed"):
                review.build_pack(self.source,self.output)
        self.assertFalse(self.output.exists())

    def test_zero_source_slide_pdf_rejected(self):
        self.make_valid_fixture()
        (self.source/"source.pdf").write_bytes(b"")
        with mock.patch.object(review.quality,"published_manifest_valid",return_value=True):
            with self.assertRaises(Exception):
                review.build_pack(self.source,self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
