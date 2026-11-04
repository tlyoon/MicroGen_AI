"""PR273 independent regression for autonomous whole-slide video segmentation."""
from pathlib import Path
import hashlib,json,tempfile,unittest,wave
from unittest import mock
import fitz
import microgen_autonomous_video_parts as parts
from microgen_quality import sha256


def scene(root,durations=(210,210,210)):
    s=root/"stage"
    s.mkdir()
    (s/"source.pdf").write_bytes(b"sha-bound-source-test")
    deck=fitz.open()
    for i,_ in enumerate(durations,1):
        page=deck.new_page()
        page.insert_text((20,30),f"Slide {i}")
    deck.save(s/"slides.pdf")
    deck.close()
    (s/"slides.mp4").write_bytes(b"FULL_H264_AAC_PLACEHOLDER")
    (s/"script_tts.json").write_text(json.dumps({"slides":[
        {"slide":i,"title":f"Topic {i}","narration":"content"}
        for i in range(1,len(durations)+1)]}),encoding="utf8")
    cache=s/".microgen_video_cache"
    cache.mkdir()
    for i,seconds in enumerate(durations,1):
        pdf=fitz.open()
        pdf.new_page().insert_text((20,30),f"Slide {i}")
        pdf.save(s/f"slide{i}.pdf")
        pdf.close()
        with wave.open(str(s/f"slide{i}.wav"),"wb") as wav:
            wav.setparams((1,2,100,seconds*100,"NONE","not compressed"))
            wav.writeframes(b"\x00\x00"*seconds*100)
        segment=cache/f"slide{i}.mp4"
        segment.write_bytes(f"MOCK-SEGMENT-{i}".encode("ascii"))
        key=hashlib.sha256(
            f"{sha256(s/f'slide{i}.pdf')}:{sha256(s/f'slide{i}.wav')}:gen_video_v22_cache_v2".encode()).hexdigest()
        (cache/f"slide{i}.json").write_text(json.dumps({
            "key":key,"sha256":sha256(segment)}),encoding="utf8")
    return s


def video_probe(path, *, expected_seconds=None, **kw):
    if not path.is_file():
        raise RuntimeError("nonexistent video")
    if expected_seconds is not None:
        return {"seconds":round(expected_seconds+0.3,3),
                "sha256":sha256(path),"audio":True,"video":True}
    return {"seconds":630.3 if path.name=="slides.mp4" else 210.3,
            "sha256":sha256(path),"audio":True,"video":True}


def fake_concat(segments,path):
    path.write_bytes(b"JOINED:"+b",".join(x.read_bytes() for x in segments))


class AutoPartsTest(unittest.TestCase):
    def test_plan_is_contiguous_and_bounded(self):
        data=[33.0]*19
        result=parts.plan_parts(data,["Velocity"]*19)
        self.assertEqual(len(result),2)
        self.assertEqual([x for group in result for x in group],list(range(1,20)))
        self.assertTrue(all(sum(data[i-1] for i in group)<=545
                            for group in result))

    def test_refuses_single_overlimit_slide(self):
        with self.assertRaises(parts.AutoPartsError):
            parts.plan_parts([400.,600.])
        with self.assertRaises(parts.AutoPartsError):
            parts.plan_parts([1.,2.],["one"])

    def test_atomic_render_idempotent_and_source_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            s=scene(Path(td))
            original=sha256(s/"slides.mp4")
            with mock.patch.object(parts,"check_video",side_effect=video_probe):
                result=parts.render_if_needed(s,fake_concat)
                self.assertEqual(len(result["parts"]),2)
                self.assertEqual([x for group in result["parts"]
                    for x in group["slides"]],[1,2,3])
                self.assertEqual(parts.verify_receipt(s)["schema_version"],1)
                self.assertEqual(parts.render_if_needed(s,fake_concat),result)
                self.assertEqual(sha256(s/"slides.mp4"),original)
                (s/"slide1.wav").write_bytes((s/"slide1.wav").read_bytes()+b"x")
                with self.assertRaises(parts.AutoPartsError):
                    parts.verify_receipt(s)

    def test_untrusted_video_cache_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            s=scene(Path(td))
            cache=s/".microgen_video_cache"/"slide2.json"
            obj=json.loads(cache.read_text())
            obj["key"]="forged"
            cache.write_text(json.dumps(obj))
            with mock.patch.object(parts,"check_video",side_effect=video_probe):
                with self.assertRaises(parts.AutoPartsError):
                    parts.render_if_needed(s,fake_concat)
                self.assertFalse((s/parts.RECEIPT).exists())
                self.assertEqual(len(list(s.glob("slides_part_*.mp4"))),0)

    def test_existing_unverified_parts_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            s=scene(Path(td))
            (s/"slides_part_01.mp4").write_bytes(b"PROTECTED")
            with mock.patch.object(parts,"check_video",side_effect=video_probe):
                with self.assertRaises(parts.AutoPartsError):
                    parts.render_if_needed(s,fake_concat)
            self.assertEqual((s/"slides_part_01.mp4").read_bytes(),b"PROTECTED")

    def test_short_full_video_stays_unsplit(self):
        with tempfile.TemporaryDirectory() as td:
            s=scene(Path(td),(10,15,20))
            def short_video(path, **kw):
                return {"seconds":45 if path.name=="slides.mp4" else 15,
                        "sha256":sha256(path),"audio":True,"video":True}
            with mock.patch.object(parts,"check_video",side_effect=short_video):
                self.assertIsNone(parts.render_if_needed(s,fake_concat))
                self.assertFalse((s/parts.RECEIPT).exists())


if __name__=="__main__":
    unittest.main()
