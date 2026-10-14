import json
import tempfile
import unittest
from pathlib import Path
from microgen_narration_batch import NarrationBatchError, generate_batched


class BatchNarrationTests(unittest.TestCase):
    def make_inputs(self, n=19):
        slides = [{"id": f"S{i}", "title": f"Topic {i}", "text": f"Equation {i}"}
                  for i in range(1, n+1)]
        source = [{"page": 1, "content": "Source-grounded integral theorem"}]
        return slides, source

    def test_large_deck_is_batched_and_reusable_without_api(self):
        s, src = self.make_inputs()
        calls = []
        def generate(part, source):
            calls.append([p["id"] for p in part])
            return {p["id"]: {"narration": p["title"], "tts_text": p["title"]} for p in part}
        with tempfile.TemporaryDirectory() as root:
            kw = dict(cache_dir=Path(root), model="gemini-3.8-flash", batch_size=8)
            a=generate_batched(s, src, generate, **kw)
            self.assertEqual([len(x) for x in calls], [8,8,3])
            b=generate_batched(s, src, generate, **kw)
            self.assertEqual(a,b)
            self.assertEqual(len(calls),3)

    def test_source_change_invalidates_previous_cache(self):
        s, src = self.make_inputs(6)
        calls=[]
        def gen(part,source):
            calls.append(1)
            return {p["id"]: {"narration": "x"} for p in part}
        with tempfile.TemporaryDirectory() as root:
            kw=dict(cache_dir=Path(root),model="gemini-3.8-flash")
            generate_batched(s,src,gen,**kw)
            generate_batched(s,[{"page":2,"content":"Changed source"}],gen,**kw)
            self.assertEqual(len(calls),2)

    def test_slide_change_invalidates_only_the_affected_batch(self):
        s,src=self.make_inputs(18)
        calls=[]
        def gen(part,source):
            calls.append(part[0]["id"])
            return {p["id"]:{"narration":p["title"]} for p in part}
        with tempfile.TemporaryDirectory() as root:
            kw=dict(cache_dir=Path(root),model="flash",batch_size=8)
            generate_batched(s,src,gen,**kw)
            s[9]["title"]="Updated verified topic"
            generate_batched(s,src,gen,**kw)
            self.assertEqual(calls,["S1","S9","S17","S9"])

    def test_failed_batch_preserves_prior_successes(self):
        s,src=self.make_inputs(17)
        calls=[]
        def fail_later(part,source):
            calls.append(part[0]["id"])
            if part[0]["id"]=="S9":
                raise TimeoutError("503")
            return {p["id"]:{"narration":p["title"]} for p in part}
        with tempfile.TemporaryDirectory() as root:
            kw=dict(cache_dir=Path(root),model="flash",batch_size=8)
            with self.assertRaises(TimeoutError):
                generate_batched(s,src,fail_later,**kw)
            self.assertEqual(len(list(Path(root).glob("*.json"))),1)
            def recover(part,source):
                calls.append(part[0]["id"])
                return {p["id"]:{"narration":p["title"]} for p in part}
            generate_batched(s,src,recover,**kw)
            self.assertEqual(calls,["S1","S9","S9","S17"])

    def test_missing_slide_is_never_cached(self):
        s,src=self.make_inputs(4)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(NarrationBatchError,"ID mismatch"):
                generate_batched(s,src,lambda part,source:{"S1":{"narration":"x"}},
                                 cache_dir=Path(root),model="flash")
            self.assertEqual(list(Path(root).glob("*.json")),[])

    def test_config_rejects_out_of_bounds_batch_sizes(self):
        s,src=self.make_inputs(2)
        for invalid in (0,-1,21):
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaisesRegex(NarrationBatchError,"between"):
                    generate_batched(s,src,lambda a,b:{},
                                     cache_dir=Path(root),model="flash",batch_size=invalid)


if __name__=="__main__":unittest.main()
