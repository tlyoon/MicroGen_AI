import tempfile
import unittest
from pathlib import Path
from PIL import Image
from microgen_figure_composition import (
    FigureCollector,FigureCompositionError,validate_figure_receipt,
)


class FigureCollectorTests(unittest.TestCase):
    def make_panel(self, root, page, index, color):
        folder=root/page
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/f"fig_{index}.png"
        Image.new("RGB",(12+index,15),color).save(path)
        return path

    def test_composite_crosses_api_batches_without_overwriting_panels(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            output=root/"pages"
            c=FigureCollector(output)
            # Actual mapper uses batches of 8; 10 crops have to combine
            # into the *same* complete Figure 2.10 output.
            originals=[]
            for idx in range(1,11):
                path=self.make_panel(root,"page_7",idx,("red" if idx%2 else "blue"))
                originals.append(path)
                c.add(output/"Figure 2.10.png",path,source_page="page_7")
            proof=c.finalize()
            self.assertEqual(len(proof["figures"]),1)
            composite=proof["figures"][0]
            self.assertEqual(composite["panel_count"],10)
            self.assertEqual(composite["size_pixels"][0],sum(12+i for i in range(1,11)))
            self.assertEqual(composite["panel_left_offsets_pixels"][1],13)
            self.assertTrue(composite["review_required"])
            self.assertEqual(len(validate_figure_receipt(output)["figures"]),1)
            with Image.open(output/"Figure 2.10.png") as im:
                self.assertEqual(im.size[0],sum(12+i for i in range(1,11)))

    def test_cross_page_same_label_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            collector=FigureCollector(root/"pages")
            collector.add(root/"pages"/"Figure 1.2.png",
                          self.make_panel(root,"page_1",1,"red"),source_page="page_1")
            with self.assertRaisesRegex(FigureCompositionError,"collision"):
                collector.add(root/"pages"/"Figure 1.2.png",
                              self.make_panel(root,"page_2",2,"blue"),source_page="page_2")

    def test_existing_composite_never_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            path=root/"pages"/"Figure 1.3.png"
            path.parent.mkdir(parents=True)
            Image.new("RGB",(20,15),"green").save(path)
            collector=FigureCollector(path.parent)
            collector.add(path,self.make_panel(root,"page_1",1,"yellow"),source_page="page_1")
            with self.assertRaisesRegex(FigureCompositionError,"conflicts"):
                collector.finalize()
            with Image.open(path) as im:
                self.assertEqual(im.getpixel((0,0)),(0,128,0))

    def test_changed_source_crop_blocks_provenance_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            path=self.make_panel(root,"page_1",1,"green")
            c=FigureCollector(root/"pages")
            c.add(root/"pages"/"Figure 1.4.png",path,source_page="page_1")
            Image.new("RGB",(30,15),"red").save(path)
            with self.assertRaisesRegex(FigureCompositionError,"changed"):
                c.finalize()

    def test_tampered_composite_fails_postpublication_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            panel=self.make_panel(root,"page_1",1,"blue")
            c=FigureCollector(root/"pages")
            path=root/"pages"/"Figure 1.5.png"
            c.add(path,panel,source_page="page_1")
            c.finalize()
            Image.new("RGB",(40,20),"black").save(path)
            with self.assertRaisesRegex(FigureCompositionError,"changed or missing"):
                validate_figure_receipt(root/"pages")

    def test_repeat_identical_crop_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            panel=self.make_panel(root,"page_1",1,"pink")
            c=FigureCollector(root/"pages")
            for i in range(3):
                c.add(root/"pages"/"Figure 1.6.png",panel,source_page="page_1")
            self.assertEqual(c.finalize()["figures"][0]["panel_count"],1)


    def test_tampered_receipt_rejects_directory_traversal(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            panel=self.make_panel(root,"page_1",1,"blue")
            collector=FigureCollector(root/"pages")
            collector.add(root/"pages"/"Figure 3.2.png",panel,source_page="page_1")
            collector.finalize()
            receipt=root/"pages"/"figure_composition_receipt.json"
            saved=json.loads(receipt.read_text(encoding="utf-8"))
            saved["figures"][0]["destination"]="../../outside.png"
            receipt.write_text(json.dumps(saved),encoding="utf-8")
            with self.assertRaisesRegex(FigureCompositionError,"unsafe destination"):
                validate_figure_receipt(root/"pages")

if __name__ == "__main__":
    unittest.main()
