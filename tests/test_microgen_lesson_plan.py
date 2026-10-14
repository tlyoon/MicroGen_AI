import unittest
from microgen_lesson_plan import Scene,PlanningError,create_plan,classify_actual_video

class PlannerTests(unittest.TestCase):
    def scenes(self,n=14):
        return [Scene(f"S{i}",f"Concept {i}",(i,),70.0,natural_break_after=(i==7))
                for i in range(1,n+1)]
    def test_global_two_part_plan(self):
        s=self.scenes()
        plan=create_plan(s)
        self.assertEqual(len(plan["parts"]),2)
        self.assertEqual(plan["parts"][0]["estimated_seconds"],520)
        self.assertEqual(plan["parts"][1]["estimated_seconds"],520)
        self.assertEqual([i for p in plan["parts"] for i in p["scene_ids"]],
                         [x.id for x in s])
        self.assertIn("preview",plan["parts"][0]["closing"])
    def test_oversize_atomic_scene_rejected(self):
        with self.assertRaisesRegex(PlanningError,"Indivisible"):
            create_plan([Scene("one","Concept",(2,),580)])
    def test_timing_gate_and_exception(self):
        for t,w in [(599.9,"passed"),(600,"review_required"),(629.9,"review_required"),(630,"blocked")]:
            self.assertEqual(classify_actual_video(t),w)
        self.assertEqual(classify_actual_video(625,approved_exception=True),"passed_exception")
        self.assertEqual(classify_actual_video(630,approved_exception=True),"blocked")
    def test_plan_hash_binds_sources(self):
        s=self.scenes(3)
        a=create_plan(s)
        s[1]=Scene("S2","New concept",(2,),70.)
        self.assertNotEqual(a["plan_sha256"],create_plan(s)["plan_sha256"])
    def test_empty_and_invalid_pages_rejected(self):
        with self.assertRaises(PlanningError):create_plan([])
        with self.assertRaises(PlanningError):create_plan([Scene("A","Concept",(0,),10.)])

if __name__=="__main__":unittest.main()
