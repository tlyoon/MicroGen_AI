import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image
import map_and_rename_v5 as mapper
from microgen_figure_composition import validate_figure_receipt


class MappingAcrossBatchesTests(unittest.TestCase):
    def test_ten_panels_from_three_gemini_batches_are_all_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            page=root/"pages"/"page_1"
            page.mkdir(parents=True)
            Image.new("RGB",(100,100),"white").save(page/"page_1.png")
            expected=0
            for i in range(1,11):
                width=10+i
                expected+=width
                Image.new("RGB",(width,13),"red" if i%2 else "blue").save(page/f"fig_{i}.png")
            def fake_generate(parts):
                if parts[0]==mapper.CAPTION_PROMPT:
                    return "Figure 2.10: Ten labelled panels"
                filenames=[re.search(r"fig_\d+\.png",part).group()
                           for part in parts if isinstance(part,str) and part.startswith("Crop file:")]
                return "\n".join(f'{name} : "Figure 2.10" : Figure 2.10.png'
                                  for name in filenames)
            previous=Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(mapper,"generate",side_effect=fake_generate), \
                     mock.patch.object(mapper,"image_part",side_effect=lambda p:p.name):
                    mapper.mapping()
            finally:
                os.chdir(previous)
            receipt=validate_figure_receipt(root)
            self.assertEqual(len(receipt["figures"]),1)
            self.assertEqual(receipt["figures"][0]["panel_count"],10)
            with Image.open(root/"Figure 2.10.png") as image:
                self.assertEqual(image.width,expected)

    def test_captioned_page_without_crops_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            p=root/"pages"/"page_1"
            p.mkdir(parents=True)
            Image.new("RGB",(20,20),"white").save(p/"page_1.png")
            previous=Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(mapper,"generate",return_value="Figure 8.1: Diagram"),\
                     mock.patch.object(mapper,"image_part",return_value="image"):
                    with self.assertRaisesRegex(RuntimeError,"no extracted crops"):
                        mapper.mapping()
            finally:
                os.chdir(previous)


    def test_completed_caption_is_reused_after_network_failure_on_later_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for index in (1,2):
                page=root/"pages"/f"page_{index}"
                page.mkdir(parents=True)
                Image.new("RGB",(35,38),"white").save(page/f"page_{index}.png")
            page2=root/"pages"/"page_2"
            Image.new("RGB",(15,20),"blue").save(page2/"fig_1.png")
            hits={"page1":0,"page2":0,"mapping":0}
            def transient_generate(parts):
                if parts[0]==mapper.CAPTION_PROMPT:
                    if parts[1]=="page_1.png":
                        hits["page1"]+=1
                        return "No figures in this chapter page"
                    hits["page2"]+=1
                    if hits["page2"]==1:
                        raise ConnectionResetError("Windows network interrupted")
                    return "Figure 8.6: textbook figure"
                hits["mapping"]+=1
                return 'fig_1.png : "Figure 8.6" : Figure 8.6.png'
            prior=Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(mapper,"generate",side_effect=transient_generate),\
                     mock.patch.object(mapper,"image_part",side_effect=lambda x:x.name):
                    with self.assertRaisesRegex(RuntimeError,"Caption extraction failed for page_2"):
                        mapper.mapping()
                    mapper.mapping()
            finally:
                os.chdir(prior)
            self.assertEqual(hits["page1"],1)
            self.assertEqual(hits["page2"],2)
            self.assertEqual(hits["mapping"],1)
            self.assertEqual(validate_figure_receipt(root)["figures"][0]["panel_count"],1)

    def test_cache_invalidation_after_image_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            prior=Path.cwd()
            try:
                os.chdir(temp)
                png=Path("p.png")
                Image.new("RGB",(12,12),"red").save(png)
                calls=[]
                def invoke():
                    calls.append(1)
                    return "No captions"
                a=mapper._cached_figure_request("p.json","prompt",[png],invoke)
                self.assertEqual(a,mapper._cached_figure_request("p.json","prompt",[png],invoke))
                self.assertEqual(len(calls),1)
                Image.new("RGB",(12,12),"blue").save(png)
                mapper._cached_figure_request("p.json","prompt",[png],invoke)
                self.assertEqual(len(calls),2)
            finally:
                os.chdir(prior)

if __name__ == "__main__":
    unittest.main()
