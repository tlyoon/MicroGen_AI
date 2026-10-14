import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import microgen_scene_proposal as p
from microgen_multipart import MultipartError


class SourceSceneProposalTests(unittest.TestCase):
    def source_and_slides(self, path):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        source = fitz.open()
        sp=source.new_page()
        sp.insert_text((70,70),"Polynomial decomposition constants are studied.")
        sp.insert_text((70,90),"Polynomial factorization method determines coefficients.")
        source.save(path/"source.pdf");source.close()
        slides=fitz.open()
        for title in ("Polynomial decomposition constants", "Polynomial factorization method"):
            page=slides.new_page()
            page.insert_text((70,70),title)
            page.insert_text((70,90),"This is the textbook derivation.")
        slides.save(path/"slides.pdf");slides.close()

    def test_proposal_is_not_prematurely_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            self.source_and_slides(stage)
            draft=p.build_proposal(stage)
            self.assertFalse(draft["reviewed"])
            self.assertEqual(len(draft["scenes"]),2)
            self.assertTrue(all(x["source_pages"] == [1] for x in draft["scenes"]))
            self.assertTrue(all(not x["needs_review"] for x in draft["scenes"]))

    def test_review_can_be_completed_before_tts_wavs_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            self.source_and_slides(stage)
            with mock.patch.object(sys,"argv",["microgen_scene_proposal.py","--stage",str(stage)]):
                self.assertEqual(p.main(),0)
            with mock.patch.object(sys,"argv",[
                "microgen_scene_proposal.py","--stage",str(stage),
                "--approve","--reviewer","Course lecturer"]):
                self.assertEqual(p.main(),0)
            approved=json.loads((stage/"lesson_scenes.json").read_text(encoding="utf-8"))
            self.assertTrue(approved["reviewed"])
            self.assertEqual(approved["reviewer"],"Course lecturer")
            self.assertFalse(any(stage.glob("slide*.wav")))

    def test_weak_citations_refuse_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            self.source_and_slides(stage)
            proposal=p.build_proposal(stage)
            proposal["scenes"][0]["needs_review"]=True
            (stage/"lesson_scenes.proposal.json").write_text(json.dumps(proposal))
            with mock.patch.object(sys,"argv",[
                "microgen_scene_proposal.py","--stage",str(stage),
                "--approve","--reviewer","Course lecturer"]):
                with self.assertRaisesRegex(MultipartError,"weakly grounded"):
                    p.main()
            self.assertFalse((stage/"lesson_scenes.json").exists())


if __name__=="__main__":
    unittest.main()
