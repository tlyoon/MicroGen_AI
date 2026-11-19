"""Opt-in real H.264 interruption/recovery acceptance on immutable owner media.

Requires MICROGEN_REAL_G3_FAULT_STAGE pointing to an ALREADY ACCEPTED, private
long lecture directory. Zero API calls. Build private same-volume hard links,
never modify any original input or output. Inject the actual expected
transaction-journal state, then test all-or-nothing rollback, tamper holds,
and completed transaction verification against the real decoded video parts.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from microgen_timed_highlight_contract import inspect_timed_highlights
from microgen_timed_long_transaction import (
    JOURNAL, _input_inventory, recover_timed_long, TimedLongTransactionError,
)
from microgen_autonomous_video_parts import RECEIPT as PARTS_RECEIPT
from microgen_measured_highlight_video_qa import RECEIPT as VISUAL_RECEIPT

# Do not assume a particular textbook or number of delivered parts.
# The authenticated real-media parts receipt determines the inventory.


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.environ.get("MICROGEN_REAL_G3_FAULT_STAGE"),
                     "Opt-in authentic private source/media recovery only")
class RealMediaRecoveryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(os.environ["MICROGEN_REAL_G3_FAULT_STAGE"]).resolve()
        cls.ffmpeg = Path(os.environ.get("MICROVID_FFMPEG")
                          or shutil.which("ffmpeg") or "missing")
        if not cls.original.is_dir() or cls.original.is_symlink():
            raise AssertionError("Real accepted source directory unavailable")
        if not cls.ffmpeg.is_file():
            raise AssertionError("Real FFmpeg required for decoded-media proof")
        cls.timed = inspect_timed_highlights(cls.original)
        cls.inventory = _input_inventory(
            cls.original, cls.timed["slide_count"], cls.timed)
        receipt=json.loads((cls.original/PARTS_RECEIPT).read_text(encoding="utf8"))
        parts=receipt.get("parts",[])
        assert isinstance(parts,list) and 2<=len(parts)<=100
        names=[part.get("file") for part in parts]
        assert names==[f"slides_part_{i:02d}.mp4"
                       for i in range(1,len(parts)+1)]
        cls.outputs_order=("slides.mp4",*names,PARTS_RECEIPT,VISUAL_RECEIPT)
        cls.outputs={
            name: digest(cls.original/name) for name in cls.outputs_order
        }
        assert cls.timed["slide_count"] > 1
        assert all((cls.original/name).is_file()
                   for name in cls.outputs_order)
        assert len(cls.inventory)<600

    def setUp(self):
        root=Path(os.environ["LOCALAPPDATA"])/"MicroGen_AI_Checkpoints"
        self.tmp=tempfile.TemporaryDirectory(
            prefix=".microgen-g3-real-media-fault-",dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.shadow=Path(self.tmp.name)/"real-source"
        self.shadow.mkdir()
        for name, expected in self.inventory.items():
            original=self.original/name
            shadow=self.shadow/name
            if original.is_symlink():
                raise AssertionError("Do not link untrusted source")
            shadow.parent.mkdir(parents=True,exist_ok=True)
            os.link(original,shadow)
            self.assertEqual(digest(shadow),expected)

    def _journal(self):
        payload={
            "schema_version":1,"publication_allowed":False,
            "input_sha256":self.inventory,
            "output_sha256":self.outputs,
        }
        (self.shadow/JOURNAL).write_text(json.dumps(payload,indent=2),
                                         encoding="utf8")

    def _link_output(self,name):
        os.link(self.original/name,self.shadow/name)
        self.assertEqual(digest(self.shadow/name),self.outputs[name])

    def _source_unchanged(self):
        for name, expected in self.inventory.items():
            self.assertEqual(digest(self.original/name),expected)
        for name, expected in self.outputs.items():
            self.assertEqual(digest(self.original/name),expected)

    def test_fault_after_two_real_h264_links_rolls_back_without_overwrite(self):
        self._journal()
        self._link_output(self.outputs_order[0])
        self._link_output(self.outputs_order[1])
        self.assertEqual(recover_timed_long(self.shadow,ffmpeg=self.ffmpeg),
                         "rolled_back_incomplete_transaction")
        self.assertFalse((self.shadow/JOURNAL).exists())
        self.assertTrue(all(not (self.shadow/name).exists()
                            for name in self.outputs_order))
        self.assertEqual(recover_timed_long(self.shadow,ffmpeg=self.ffmpeg),
                         "no_pending_transaction")
        self._source_unchanged()

    def test_unrecognized_media_survives_and_fails_closed(self):
        self._journal()
        outside=self.shadow/self.outputs_order[0]
        outside.write_bytes(b"UNRELATED_PRIVATE_MEDIA_MUST_BE_PROTECTED")
        saved=digest(outside)
        with self.assertRaisesRegex(
                TimedLongTransactionError,
                "Unrelated or modified media is protected"):
            recover_timed_long(self.shadow,ffmpeg=self.ffmpeg)
        self.assertEqual(digest(outside),saved)
        self.assertTrue((self.shadow/JOURNAL).exists())
        self._source_unchanged()

    def test_complete_real_parts_are_reverified_before_journal_cleanup(self):
        self._journal()
        for name in self.outputs_order:
            self._link_output(name)
        self.assertEqual(recover_timed_long(self.shadow,ffmpeg=self.ffmpeg),
                         "completed_verified_transaction")
        self.assertFalse((self.shadow/JOURNAL).exists())
        for name,expected in self.outputs.items():
            self.assertEqual(digest(self.shadow/name),expected)
        self._source_unchanged()


if __name__=="__main__":
    unittest.main()
