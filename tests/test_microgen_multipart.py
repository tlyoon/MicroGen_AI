import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock
from microgen_multipart import MultipartError, plan_parts, validate_scenes, render_parts
from microgen_quality import sha256


class MultipartPlanningTests(unittest.TestCase):
    def scenes(self, lengths=(4,4,4,4)):
        result=[]
        offset=1
        for n,i in enumerate(lengths):
            result.append({
                "slides":list(range(offset,offset+i)),
                "topic":f"Concept {n+1}",
                "source_pages":[1],
                "natural_break_after":True,
            })
            offset+=i
        return result

    def test_parts_only_end_at_semantic_boundaries(self):
        scenes=self.scenes()
        durations=[60.0]*16
        plan=plan_parts(scenes,durations,max_seconds=570)
        self.assertEqual(len(plan),2)
        self.assertEqual([p["slides"][-1] for p in plan],[8,16])
        self.assertTrue(all(p["boundary_verified"] for p in plan))
        self.assertEqual(sum(p["duration_seconds"] for p in plan),960)

    def test_refuses_split_inside_indivisible_scene(self):
        scenes=self.scenes((11,5))
        with self.assertRaisesRegex(MultipartError,"indivisible concept"):
            plan_parts(scenes,[60.0]*16,max_seconds=570)

    def test_only_allowed_boundaries_may_be_selected(self):
        scenes=self.scenes((3,3,3,3))
        scenes[0]["natural_break_after"]=False
        plan=plan_parts(scenes,[58.0]*12,max_seconds=570)
        self.assertNotIn(3,[p["slides"][-1] for p in plan[:-1]])

    def test_corrupt_duration_budget_fails(self):
        with self.assertRaisesRegex(MultipartError,"Invalid part timing"):
            plan_parts(self.scenes((2,)),[30.,30.],max_seconds=610)

    def test_source_hash_and_review_are_required(self):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,number in (("source.pdf",2),("slides.pdf",4)):
                doc=fitz.open()
                for n in range(number):
                    pg=doc.new_page();pg.insert_text((70,70),f"Example source {n}")
                doc.save(root/name)
                doc.close()
            manifest={
                "schema_version":1,"reviewed":False,"reviewer":"",
                "source_sha256":sha256(root/"source.pdf"),
                "slides_sha256":sha256(root/"slides.pdf"),
                "scenes":[{"topic":"Fractions","slides":[1,2],"source_pages":[1],
                           "natural_break_after":True},
                          {"topic":"Antiderivatives","slides":[3,4],"source_pages":[2],
                           "natural_break_after":True}],
            }
            path=root/"lesson_scenes.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(MultipartError,"reviewer approval"):
                validate_scenes(root,durations=[100]*4)
            manifest.update(reviewed=True,reviewer="Course expert")
            path.write_text(json.dumps(manifest))
            scenes,durations=validate_scenes(root,durations=[100]*4)
            self.assertEqual(len(scenes),2)
            self.assertEqual(sum(durations),400)
            manifest["slides_sha256"]="old"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(MultipartError,"Slide deck changed"):
                validate_scenes(root,durations=[100]*4)

    def test_part_render_receipt_reuses_valid_media(self):
        # Fast isolated simulation: real source PDFs/WAVs but mocked FFmpeg probes.
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,size in (("source.pdf",2),("slides.pdf",4)):
                doc=fitz.open()
                for n in range(size):
                    p=doc.new_page();p.insert_text((70,70),f"Topic {n}")
                doc.save(root/name);doc.close()
            for i in range(1,5):
                with wave.open(str(root/f"slide{i}.wav"),"wb") as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000)
                    w.writeframes(b"\0\0"*(8000*100))
            manifest={"schema_version":1,"reviewed":True,"reviewer":"Course expert",
                "source_sha256":sha256(root/"source.pdf"),
                "slides_sha256":sha256(root/"slides.pdf"),
                "scenes":[{"topic":"First","slides":[1,2],"source_pages":[1],"natural_break_after":True},
                          {"topic":"Second","slides":[3,4],"source_pages":[2],"natural_break_after":True}]}
            (root/"lesson_scenes.json").write_text(json.dumps(manifest))
            segments=[]
            for i in range(1,5):
                p=root/f"seg{i}.mp4";p.write_bytes(f"segment-{i}".encode());segments.append(p)
            concat_calls=[]
            def concat(group,target):
                concat_calls.append([x.name for x in group])
                Path(target).write_bytes(("concat"+str(len(group))).encode())
            def fake_check(path,expected_seconds=None):
                name=Path(path).name
                actual=float(expected_seconds or 200.0)
                return {"seconds":actual,"sha256":sha256(path),"audio":True,"video":True}
            with mock.patch("microgen_multipart.check_video",side_effect=fake_check):
                one=render_parts(root,segments,concat,max_seconds=300,target_seconds=250)
                two=render_parts(root,segments,concat,max_seconds=300,target_seconds=250)
            self.assertEqual(len(one["parts"]),2)
            self.assertEqual(len(two["parts"]),2)
            self.assertEqual(len(concat_calls),2)
            self.assertEqual([p["slides"] for p in one["parts"]],[[1,2],[3,4]])


if __name__=="__main__":
    unittest.main()
