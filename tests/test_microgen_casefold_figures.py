"""Canonical figure filenames prevent Windows case-insensitive duplicate promotions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import microgen_quality as q


class FigureCasefoldTests(unittest.TestCase):
    def test_repeated_references_emit_one_canonical_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            file=root/"Figure 8.2.png"
            file.write_bytes(b"image-bytes")
            names=q.canonical_figure_hashes([file,file,file])
            self.assertEqual(names,{"Figure 8.2.png":q.sha256(file)})

    def test_uppercase_alias_resolves_to_actual_spelling_on_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            actual=root/"Figure 8.2.png"
            actual.write_bytes(b"diagram")
            upper=root/"FIGURE 8.2.png"
            if not upper.is_file():
                self.skipTest("Filesystem is case-sensitive; uppercase alias is different")
            result=q.canonical_figure_hashes([upper,actual])
            self.assertEqual(result,{"Figure 8.2.png":q.sha256(actual)})

    def test_distinct_files_with_casefold_collision_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            upper=root/"FIGURE 8.2.png"
            title=root/"Figure 8.2.png"
            upper.write_bytes(b"first")
            title.write_bytes(b"second")
            if upper.resolve()==title.resolve():
                self.skipTest("Case-insensitive filesystem cannot hold distinct colliders")
            with self.assertRaisesRegex(q.QualityError,"Case-insensitive figure filename collision"):
                q.canonical_figure_hashes([upper,title])

    def test_reject_casefold_duplicate_from_external_publication_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            stage,dest=root/"stage",root/"dest"
            stage.mkdir();dest.mkdir()
            for name in ("source.pdf","slides.pdf","slides.tex","script.txt",
                         "script_tts.json","slides.mp4","Figure 8.2.png"):
                (stage/name).write_bytes(name.encode())
            (dest/"source.pdf").write_bytes((stage/"source.pdf").read_bytes())
            manifest={
                "schema_version":1,
                "source_sha256":q.sha256(stage/"source.pdf"),
                "figure_sha256":{
                    "Figure 8.2.png":q.sha256(stage/"Figure 8.2.png"),
                    "FIGURE 8.2.png":q.sha256(stage/"Figure 8.2.png"),
                }
            }
            with self.assertRaisesRegex(q.QualityError,"Case-insensitive duplicate figure names"):
                q.publish_bundle(stage,dest,manifest=manifest)
            self.assertFalse((dest/".microgen_verified_completion.json").exists())
            self.assertEqual(sorted(p.name for p in dest.iterdir()),["source.pdf"])

    def test_existing_manifest_with_casefold_duplicate_fails_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ("source.pdf","slides.pdf","slides.tex","script.txt",
                         "script_tts.json","slides.mp4","Figure 8.2.png"):
                (root/name).write_bytes(name.encode())
            manifest={
                "schema_version":1,
                "source_sha256":q.sha256(root/"source.pdf"),
                "slides_pdf_sha256":q.sha256(root/"slides.pdf"),
                "slides_tex_sha256":q.sha256(root/"slides.tex"),
                "script_sha256":q.sha256(root/"script.txt"),
                "sidecar_sha256":q.sha256(root/"script_tts.json"),
                "mp4_sha256":q.sha256(root/"slides.mp4"),
                "figure_sha256":{
                    "Figure 8.2.png":q.sha256(root/"Figure 8.2.png"),
                    "FIGURE 8.2.png":q.sha256(root/"Figure 8.2.png"),
                },
            }
            (root/".microgen_verified_completion.json").write_text(json.dumps(manifest))
            self.assertFalse(q.published_manifest_valid(root))


if __name__=="__main__":
    unittest.main()
