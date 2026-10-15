"""Regression for transient disappearance of destination-local publish candidates."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_quality as q


class CandidateRestageTests(unittest.TestCase):
    def fixtures(self, root):
        stage, dest = Path(root)/"stage", Path(root)/"dest"
        stage.mkdir()
        dest.mkdir()
        names=("source.pdf","slides.pdf","slides.tex","script.txt",
               "script_tts.json","slides.mp4","Figure 8.2.png")
        for name in names:
            (stage/name).write_bytes(("new-"+name).encode())
            (dest/name).write_bytes(("old-"+name).encode())
        (dest/"source.pdf").write_bytes((stage/"source.pdf").read_bytes())
        manifest={
            "schema_version":1,
            "source_sha256":q.sha256(stage/"source.pdf"),
            "slides_pdf_sha256":q.sha256(stage/"slides.pdf"),
            "slides_tex_sha256":q.sha256(stage/"slides.tex"),
            "script_sha256":q.sha256(stage/"script.txt"),
            "sidecar_sha256":q.sha256(stage/"script_tts.json"),
            "mp4_sha256":q.sha256(stage/"slides.mp4"),
            "figure_sha256":{"Figure 8.2.png":q.sha256(stage/"Figure 8.2.png")},
        }
        return stage,dest,manifest,names

    def test_one_missing_candidate_is_restaged_and_verified(self):
        with tempfile.TemporaryDirectory() as root:
            stage,dest,manifest,names=self.fixtures(root)
            original=Path.replace
            state={"lost":0}
            def missing_once(path,target):
                if (path.name.startswith("Figure 8.2.png.microgen-")
                        and path.name.endswith(".candidate") and state["lost"]==0):
                    path.unlink()
                    state["lost"]+=1
                    raise FileNotFoundError(2,"candidate vanished",str(path))
                return original(path,target)
            with mock.patch.object(Path,"replace",autospec=True,side_effect=missing_once):
                q.publish_bundle(stage,dest,manifest=manifest)
            self.assertEqual(state["lost"],1)
            self.assertTrue(q.published_manifest_valid(dest))
            self.assertEqual((dest/"Figure 8.2.png").read_bytes(),(stage/"Figure 8.2.png").read_bytes())
            self.assertFalse(list(dest.glob("*.candidate")))

    def test_persistent_missing_candidate_fails_closed_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as root:
            stage,dest,manifest,names=self.fixtures(root)
            original=Path.replace
            state={"attempts":0}
            def always_missing(path,target):
                if path.name.startswith("Figure 8.2.png.microgen-") and path.name.endswith(".candidate"):
                    state["attempts"]+=1
                    path.unlink(missing_ok=True)
                    raise FileNotFoundError(2,"candidate vanished",str(path))
                return original(path,target)
            with mock.patch.object(Path,"replace",autospec=True,side_effect=always_missing):
                with self.assertRaises(FileNotFoundError):
                    q.publish_bundle(stage,dest,manifest=manifest)
            self.assertEqual(state["attempts"],2)
            self.assertFalse((dest/".microgen_verified_completion.json").exists())
            for name in names[1:]:
                self.assertEqual((dest/name).read_bytes(),("old-"+name).encode())
            self.assertFalse(list(dest.glob("*.candidate")))

    def test_source_drift_on_restage_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            stage,dest,manifest,names=self.fixtures(root)
            original=Path.replace
            def drift(path,target):
                if path.name.startswith("Figure 8.2.png.microgen-") and path.name.endswith(".candidate"):
                    path.unlink(missing_ok=True)
                    (stage/"Figure 8.2.png").write_bytes(b"unexpected new content")
                    raise FileNotFoundError(2,"candidate vanished",str(path))
                return original(path,target)
            with mock.patch.object(Path,"replace",autospec=True,side_effect=drift):
                with self.assertRaisesRegex(q.QualityError,"Source changed during re-stage"):
                    q.publish_bundle(stage,dest,manifest=manifest)
            self.assertFalse((dest/".microgen_verified_completion.json").exists())
            for name in names[1:]:
                self.assertEqual((dest/name).read_bytes(),("old-"+name).encode())


if __name__=="__main__":
    unittest.main()
