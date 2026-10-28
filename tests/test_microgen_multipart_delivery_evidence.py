"""Independent multipart delivery binding tests, no FFmpeg or billed calls."""
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from microgen_multipart_delivery_evidence import (
    MultipartEvidenceError, verify_multipart_delivery,
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class MultipartDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)/"source"
        self.base.mkdir()
        self.media=Path(self.temp.name)/"media"
        self.media.mkdir()
        self.qa_dir=Path(self.temp.name)/"audit"
        self.qa_dir.mkdir()
        self.source={"slide_count":2,"slides_pdf_sha256":"a"*64,
            "wav_inventory":[{"slide":1,"wav_sha256":"1"*64},
                             {"slide":2,"wav_sha256":"2"*64}]}
        pcm=b"\x10\x05"*24000
        self.parts=[]
        self.qa_parts=[]
        for i in (1,2):
            video=self.media/f"part{i}.mp4"
            video.write_bytes(f"real-video-{i}".encode())
            audio=self.media/f"part{i}.wav"
            with wave.open(str(audio),"wb") as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
                f.writeframes(pcm)
            audio_hash=hashlib.sha256(pcm).hexdigest()
            self.parts.append({"part":i,"slides":[i,i],"video_file":video.name,
                "audio_file":audio.name,"video_sha256":sha(video),
                "input_wav_sha256":[self.source["wav_inventory"][i-1]["wav_sha256"]],
                "raw_audio_pcm_sha256":audio_hash,"seconds":25.0})
            self.qa_parts.append({"part":i,"mp4_sha256":sha(video),
                                   "decoded_audio_pcm_sha256":audio_hash})
        self.master={"source":self.source,"source_pdf_sha256":self.source["slides_pdf_sha256"],
                     "parts":self.parts,"publication_allowed":False,
                     "spoken_equation_figure_semantics_verified":False}
        self.check={"source":self.source,"parts":self.qa_parts,
                    "full_pcm_hash_matches":True,
                    "mathematical_figure_alignment_verified":False,
                    "publication_allowed":False}
        self.master_path=self.media/"receipt.json"
        self.check_path=self.qa_dir/"independent.json"

    def run_check(self, duration=25.0):
        self.master_path.write_text(json.dumps(self.master))
        self.check_path.write_text(json.dumps(self.check))
        videos={"all_videos_under_600_seconds":duration<600,
                "videos":[{"video_sha256":row["video_sha256"],
                           "duration_seconds":duration} for row in self.parts]}
        with patch("microgen_multipart_delivery_evidence.source_inventory",
                   return_value=(self.base,self.source)),patch(
                   "microgen_multipart_delivery_evidence.audit_videos",
                   return_value=videos):
            return verify_multipart_delivery(self.base,self.master_path,self.check_path)

    def test_two_contiguous_source_bound_videos_pass_technical_only(self):
        result=self.run_check()
        self.assertEqual(result["part_count"],2)
        self.assertTrue(result["technical_multipart_av_pass"])
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["narration_to_equation_or_figure_sync_verified"])

    def test_missing_slide_fails(self):
        self.parts[1]["slides"]=[3,3]
        with self.assertRaises(MultipartEvidenceError):
            self.run_check()

    def test_tampered_media_hash_fails(self):
        (self.media/"part1.mp4").write_bytes(b"tampered")
        with self.assertRaises(MultipartEvidenceError):
            self.run_check()

    def test_bad_original_audio_hash_fails(self):
        self.parts[0]["raw_audio_pcm_sha256"]="0"*64
        with self.assertRaises(MultipartEvidenceError):
            self.run_check()

    def test_forged_academic_promotion_fails(self):
        self.master["publication_allowed"]=True
        with self.assertRaises(MultipartEvidenceError):
            self.run_check()

    def test_overlong_part_rejected(self):
        with self.assertRaises(MultipartEvidenceError):
            self.run_check(duration=600.0)


if __name__=="__main__":
    unittest.main()
