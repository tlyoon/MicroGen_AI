"""HP-local and hosted offline tests: long-timed media promotion is fail closed.

Exercises the actual existing part/visual receipt validators with synthetic
placeholder encoded bytes and controlled decoded frames. Independent real
FFmpeg integration is separately covered by short-lecture media tests.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from PIL import ImageDraw

import gen_video_v22 as renderer
import microgen_autonomous_video_parts as parts
import microgen_measured_highlight_video_qa as visual
import microgen_timed_long_transaction as txn
from microgen_quality import sha256
from microgen_timed_highlight_contract import (
    inspect_timed_highlights, video_segment_cache_key,
)
from test_microgen_timed_highlight_contract import stage as sample_stage


def fake_concat(segments: list[Path], destination: Path) -> None:
    destination.write_bytes(b"JOINED:"+
                            b",".join(x.read_bytes() for x in segments))


class TimedLongTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=sample_stage(Path(self.tmp.name))
        (self.stage/"source.pdf").write_bytes((self.stage/"slides.pdf").read_bytes())
        self.ffmpeg=Path(sys.executable)
        self.timed=inspect_timed_highlights(self.stage)
        self.fake=copy.deepcopy(self.timed)
        for row in self.fake["slides"]:
            row["duration_seconds"]=301.0
            row["elements"][0]["start_seconds"]=0.0
            row["elements"][0]["end_seconds"]=150.0
            row["elements"][1]["start_seconds"]=150.0
            row["elements"][1]["end_seconds"]=301.0
        self.wavs={"seconds":[301.,301.],"total_seconds":602.0,
                   "sha256":[sha256(self.stage/f"slide{i}.wav") for i in (1,2)]}
        cache=self.stage/f".microgen_video_cache_timed_{self.timed['manifest_sha256'][:12]}"
        cache.mkdir()
        self.segments=[]
        for i in (1,2):
            segment=cache/f"slide{i}.mp4"
            segment.write_bytes(f"PRIVATE_SOURCE_SLIDE_{i}".encode())
            metadata=cache/f"slide{i}.json"
            key=video_segment_cache_key(
                self.stage/f"slide{i}.pdf",self.stage/f"slide{i}.wav",
                self.timed["manifest_sha256"])
            metadata.write_text(json.dumps({"key":key,"sha256":sha256(segment)}),
                                encoding="utf8")
            self.segments.append(segment)
        self.candidate=self.stage/"slides.candidate.mp4"
        fake_concat(self.segments,self.candidate)
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.patch= self.stack.enter_context
        self.patch(mock.patch.object(txn,"check_video",side_effect=self.probe))
        self.patch(mock.patch.object(txn,"check_wavs",return_value=self.wavs))
        self.patch(mock.patch.object(parts,"check_video",side_effect=self.probe))
        self.patch(mock.patch.object(parts,"check_wavs",return_value=self.wavs))
        self.patch(mock.patch.object(visual,"check_video",side_effect=self.probe))
        self.patch(mock.patch.object(visual,"inspect_timed_highlights",
                                     return_value=self.fake))
        self.patch(mock.patch.object(visual,"_frame",side_effect=self.frame))

    @staticmethod
    def probe(path,*,expected_seconds=None,**kwargs):
        name=Path(path).name
        if expected_seconds is not None:
            return {"seconds":float(expected_seconds),
                    "sha256":sha256(path),"audio":True,"video":True}
        return {"seconds":602.0 if name in
                ("slides.mp4","slides.candidate.mp4") else 301.0,
                "sha256":sha256(path),"audio":True,"video":True}

    def frame(self,ffmpeg,path,when):
        import fitz
        slide=1 if Path(path).name=="slides_part_01.mp4" else 2
        self.assertGreaterEqual(when,0.0)
        self.assertLess(when,301.0)
        with fitz.open(self.stage/"slides.pdf") as doc:
            page=doc[slide-1]
            output=visual._pdf_reference(page)
            cue=self.fake["slides"][slide-1]["elements"][0 if when<150 else 1]
            ImageDraw.Draw(output).rectangle(
                visual._pixel_box(page,cue),fill=(255,255,85))
        return output

    def promote(self,concat=fake_concat):
        return txn.promote_timed_long(
            self.stage,self.segments,self.candidate,concat,ffmpeg=self.ffmpeg)

    def test_all_parts_accepted_before_any_final_media_promotion(self):
        result=self.promote()
        self.assertEqual(result["status"],
                         "PRIVATE_SOURCE_PCM_TIMED_LONG_VIDEO_VERIFIED")
        self.assertEqual(result["parts"],2)
        self.assertEqual(result["cues"],4)
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(parts.verify_receipt(self.stage)["schema_version"],1)
        self.assertEqual(visual.verify_receipt(self.stage,ffmpeg=self.ffmpeg)
                         ["cue_count"],4)
        original=sha256(self.stage/"slides.mp4")
        with self.assertRaisesRegex(txn.TimedLongTransactionError,
                                    "Previous final media"):
            self.promote()
        self.assertEqual(sha256(self.stage/"slides.mp4"),original)

    def test_static_video_candidate_never_reaches_final_files(self):
        import fitz
        def static_frame(ffmpeg,path,when):
            with fitz.open(self.stage/"slides.pdf") as deck:
                slide=1 if path.name.endswith("_01.mp4") else 2
                return visual._pdf_reference(deck[slide-1])
        self.patch(mock.patch.object(visual,"_frame",side_effect=static_frame))
        with self.assertRaisesRegex(visual.MeasuredVisualQAError,
                                    "no independently visible"):
            self.promote()
        self.assertFalse((self.stage/"slides.mp4").exists())
        self.assertFalse(list(self.stage.glob("slides_part_*.mp4")))
        self.assertFalse((self.stage/parts.RECEIPT).exists())
        self.assertFalse((self.stage/visual.RECEIPT).exists())

    def test_preexisting_accepted_file_preserved_without_rendering(self):
        before=self.stage/"slides.mp4"
        before.write_bytes(b"PREVIOUS_STATIC_ACCEPTED_VIDEO")
        checksum=sha256(before)
        recorded=[]
        with self.assertRaisesRegex(txn.TimedLongTransactionError,
                                    "Previous final media"):
            self.promote(lambda segs,target:recorded.append(target))
        self.assertEqual(recorded,[])
        self.assertEqual(sha256(before),checksum)

    def test_partial_render_exception_leaves_no_outputs(self):
        def broken_concat(segments,destination):
            if destination.name.endswith("_02.mp4"):
                raise RuntimeError("Transient render failure")
            fake_concat(segments,destination)
        with self.assertRaisesRegex(RuntimeError,"Transient render"):
            self.promote(broken_concat)
        self.assertFalse((self.stage/"slides.mp4").exists())
        self.assertFalse(list(self.stage.glob("slides_part_*.mp4")))

    def test_changed_source_during_render_refused(self):
        original=self.stage/"script_tts.json"
        before=sha256(original)
        def mutate_input(segments,destination):
            if destination.name.endswith("_02.mp4"):
                original.write_bytes(original.read_bytes()+b" ")
            fake_concat(segments,destination)
        with self.assertRaises(Exception):
            self.promote(mutate_input)
        self.assertNotEqual(sha256(original),before)
        self.assertFalse((self.stage/"slides.mp4").exists())
        self.assertFalse(list(self.stage.glob("slides_part_*.mp4")))

    def test_concurrent_file_race_does_not_overwrite_or_leave_partial(self):
        original=txn._link
        raced=self.stage/"slides_part_02.mp4"
        def race(source,destination):
            if destination==raced:
                raced.write_bytes(b"CONCURRENT_UNRELATED_VIDEO")
            return original(source,destination)
        self.patch(mock.patch.object(txn,"_link",side_effect=race))
        with self.assertRaises(FileExistsError):
            self.promote()
        self.assertEqual(raced.read_bytes(),b"CONCURRENT_UNRELATED_VIDEO")
        self.assertFalse((self.stage/"slides.mp4").exists())
        self.assertFalse((self.stage/"slides_part_01.mp4").exists())
        self.assertFalse((self.stage/parts.RECEIPT).exists())

    def test_uncaught_process_termination_rolls_back_only_journaled_bytes(self):
        original=txn._link
        final_part=self.stage/"slides_part_02.mp4"
        def terminate_mid_commit(source,destination):
            if destination==final_part:
                raise SystemExit("simulated hard process interruption")
            return original(source,destination)
        self.patch(mock.patch.object(txn,"_link",side_effect=terminate_mid_commit))
        with self.assertRaises(SystemExit):
            self.promote()
        self.assertTrue((self.stage/txn.JOURNAL).exists())
        self.assertTrue((self.stage/"slides.mp4").exists())
        # Return to the real exclusive writer (the interrupted process ended).
        self.stack.pop_all().close()
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.assertEqual(txn.recover_timed_long(
            self.stage,ffmpeg=self.ffmpeg),"rolled_back_incomplete_transaction")
        self.assertFalse((self.stage/txn.JOURNAL).exists())
        self.assertFalse((self.stage/"slides.mp4").exists())
        self.assertFalse((self.stage/"slides_part_01.mp4").exists())

    def test_interrupted_transaction_does_not_remove_modified_media(self):
        original=txn._link
        part=self.stage/"slides_part_02.mp4"
        def terminate(source,destination):
            if destination==part:
                raise SystemExit("interrupted")
            return original(source,destination)
        with mock.patch.object(txn,"_link",side_effect=terminate):
            with self.assertRaises(SystemExit):
                self.promote()
        protected=self.stage/"slides.mp4"
        protected.write_bytes(b"UNKNOWN-CONCURRENT-REPLACEMENT")
        with self.assertRaisesRegex(txn.TimedLongTransactionError,
                                    "Unrelated or modified media"):
            txn.recover_timed_long(self.stage,ffmpeg=self.ffmpeg)
        self.assertEqual(protected.read_bytes(),b"UNKNOWN-CONCURRENT-REPLACEMENT")
        self.assertTrue((self.stage/txn.JOURNAL).exists())

    def test_recovery_keeps_verified_complete_delivery(self):
        result=self.promote()
        originals={name:sha256(self.stage/name) for name in (
            "slides.mp4","slides_part_01.mp4","slides_part_02.mp4",
            parts.RECEIPT,visual.RECEIPT)}
        state={
            "schema_version":1,"publication_allowed":False,
            "input_sha256":txn._input_inventory(
                self.stage,2,self.timed),
            "output_sha256":originals,
        }
        (self.stage/txn.JOURNAL).write_text(json.dumps(state),encoding="utf8")
        self.assertEqual(txn.recover_timed_long(
            self.stage,ffmpeg=self.ffmpeg),"completed_verified_transaction")
        self.assertFalse((self.stage/txn.JOURNAL).exists())
        self.assertEqual({n:sha256(self.stage/n) for n in originals},originals)

    def test_changed_source_during_recovery_blocks_cleanup(self):
        original=txn._link
        part=self.stage/"slides_part_02.mp4"
        def terminate(source,destination):
            if destination==part:
                raise SystemExit("interrupted")
            return original(source,destination)
        with mock.patch.object(txn,"_link",side_effect=terminate):
            with self.assertRaises(SystemExit):
                self.promote()
        self.assertTrue((self.stage/"slides.mp4").exists())
        (self.stage/"script_tts.json").write_bytes(b"changed-source")
        with self.assertRaisesRegex(txn.TimedLongTransactionError,
                                    "Source changed|source"):
            txn.recover_timed_long(self.stage,ffmpeg=self.ffmpeg)
        self.assertTrue((self.stage/"slides.mp4").exists())
        self.assertTrue((self.stage/txn.JOURNAL).exists())

    def test_invalid_cached_segment_sha_prevents_promotion(self):
        metadata=self.stage/f".microgen_video_cache_timed_{self.timed['manifest_sha256'][:12]}"/"slide2.json"
        entry=json.loads(metadata.read_text())
        entry["sha256"]="0"*64
        metadata.write_text(json.dumps(entry))
        with self.assertRaises(Exception):
            self.promote()
        self.assertFalse((self.stage/"slides.mp4").exists())

    def test_renderer_long_candidate_is_routed_to_transaction(self):
        from microgen_quality import check_video as actual_probe
        with mock.patch.object(renderer,"_make_segment",
                               side_effect=lambda p,a,o,**kw:o.write_bytes(b"SEGMENT")), \
             mock.patch.object(renderer,"_concat",side_effect=fake_concat), \
             mock.patch("microgen_quality.check_video",side_effect=self.probe), \
             mock.patch("microgen_quality.check_wavs",return_value=self.wavs), \
             mock.patch("microgen_timed_long_transaction.promote_timed_long",
                        return_value={"parts":2}) as routed, \
             mock.patch("microgen_runtime_preflight.find_h264_ffmpeg",
                        return_value=str(self.ffmpeg)), \
             mock.patch.dict("os.environ",{"MICROVID_FFMPEG":str(self.ffmpeg)}):
            from os import chdir, getcwd
            previous=getcwd()
            chdir(self.stage)
            try:
                renderer.main()
            finally:
                chdir(previous)
        routed.assert_called_once()
        self.assertFalse(self.candidate.exists())


if __name__=="__main__":
    unittest.main()


def test_timed_transaction_code_invalidates_video_checkpoint(tmp_path):
    from microgen_quality import dependency_fingerprint
    stage=sample_stage(tmp_path)
    for name in ("gen_video_v22.py",
                 "microgen_autonomous_video_parts.py",
                 "microgen_timed_highlight_contract.py"):
        (stage/name).write_text("code-unchanged",encoding="utf8")
    before=dependency_fingerprint(stage,"video")
    transaction=stage/"microgen_timed_long_transaction.py"
    transaction.write_text("new transactional renderer",encoding="utf8")
    after=dependency_fingerprint(stage,"video")
    assert before!=after
    transaction.write_text("revised transactional renderer",encoding="utf8")
    assert dependency_fingerprint(stage,"video")!=after
