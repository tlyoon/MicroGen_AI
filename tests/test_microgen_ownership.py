import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from microgen_ownership import GCSLease, LeaseBusy, LeaseLost, lease_object_key
import microgen_batch


class PreconditionFailed(Exception):
    code=412
class NotFound(Exception):
    pass

class FakeBucket:
    def __init__(self):
        self.state={}
        self.next_generation=1
    def blob(self,key):
        return FakeBlob(self,key)

class FakeBlob:
    def __init__(self,bucket,key):
        self.bucket=bucket;self.key=key;self.generation=None
    def reload(self):
        if self.key not in self.bucket.state:raise NotFound()
        self.generation=self.bucket.state[self.key][0]
    def download_as_bytes(self):
        self.reload()
        return self.bucket.state[self.key][1]
    def upload_from_string(self,data,content_type,if_generation_match):
        current=self.bucket.state.get(self.key)
        actual=0 if current is None else current[0]
        if if_generation_match!=actual:raise PreconditionFailed()
        gen=self.bucket.next_generation
        self.bucket.next_generation+=1
        self.bucket.state[self.key]=(gen,data.encode())
        self.generation=gen
    def delete(self,if_generation_match):
        current=self.bucket.state.get(self.key)
        actual=0 if current is None else current[0]
        if current is None:raise NotFound()
        if if_generation_match!=actual:raise PreconditionFailed()
        del self.bucket.state[self.key]


class OwnershipTests(unittest.TestCase):
    def test_atomic_second_worker_rejected(self):
        bucket=FakeBucket()
        now=[1000.]
        mk=lambda token:GCSLease(bucket,"thomas2627","8.5",clock=lambda:now[0],
                      token=token,run_heartbeat=False)
        a=mk("computer-a")
        b=mk("computer-b")
        a.acquire()
        with self.assertRaises(LeaseBusy):
            b.acquire()
        a.assert_held()
        a.release()
        b.acquire()
        b.assert_held()
        b.release()

    def test_expired_takeover_fences_previous_writer(self):
        bucket=FakeBucket();now=[300.]
        mk=lambda token:GCSLease(bucket,"physics","1.1",clock=lambda:now[0],
                        token=token,run_heartbeat=False)
        a=mk("old");a.acquire()
        now[0]+=205
        b=mk("new");b.acquire()
        with self.assertRaises(LeaseLost):
            a.assert_held()
        a.release()   # Must not delete successor's lease.
        b.assert_held()
        b.release()
        self.assertEqual(bucket.state,{})

    def test_compare_and_swap_generation_blocks_stale_replacement(self):
        b=FakeBucket();now=[100.]
        a=GCSLease(b,"course","9.4",clock=lambda:now[0],run_heartbeat=False)
        a.acquire()
        raw=b.state[a.key]
        with self.assertRaises(PreconditionFailed):
            b.blob(a.key).upload_from_string("foreign",content_type="application/json",
                                            if_generation_match=raw[0]-1)
        a.release()

    def test_key_rejects_unsafe_path_identifiers(self):
        for bad in ("../project","x/y",""):
            with self.assertRaises(ValueError):lease_object_key(bad,"1.1")
        with self.assertRaises(ValueError):lease_object_key("campaign","../8.5")

    def test_single_pc_local_lock_is_exclusive_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(work_root=Path(tmp),multi_pc=False)
            with microgen_batch.subchapter_ownership(args,"8.5"):
                with self.assertRaisesRegex(RuntimeError,"active local worker"):
                    with microgen_batch.subchapter_ownership(args,"8.5"):
                        pass
            # A stable lock inode remains, but its OS lock is released.
            self.assertTrue((Path(tmp)/".microgen_8.5.owner.lock").exists())
            with microgen_batch.subchapter_ownership(args, "8.5"):
                pass


    def test_crashed_local_worker_releases_kernel_lock(self):
        import subprocess
        import sys
        import os
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            acquired=root/"ready.signal"
            source=(
                "from types import SimpleNamespace\n"
                "from pathlib import Path\n"
                "from microgen_batch import subchapter_ownership\n"
                "import time\n"
                f"args=SimpleNamespace(work_root=Path({str(root)!r}),multi_pc=False)\n"
                "with subchapter_ownership(args,'4.2'):\n"
                f" Path({str(acquired)!r}).write_text('locked')\n"
                " time.sleep(60)\n"
            )
            proc=subprocess.Popen(
                [sys.executable, "-u", "-c", source],
                cwd=str(Path(__file__).resolve().parent.parent),
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:
                until=time.monotonic()+12
                while not acquired.is_file() and time.monotonic()<until:
                    if proc.poll() is not None:
                        raise AssertionError(f"Child lock failed: {proc.stderr.read()!r}")
                    time.sleep(.1)
                self.assertTrue(acquired.is_file())
                args=SimpleNamespace(work_root=root,multi_pc=False)
                with self.assertRaisesRegex(RuntimeError,"active local worker"):
                    with microgen_batch.subchapter_ownership(args,"4.2"):
                        pass
                proc.kill()
                proc.wait(timeout=5)
                with microgen_batch.subchapter_ownership(args,"4.2"):
                    pass
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                if proc.stderr is not None:
                    proc.stderr.close()

if __name__=="__main__":
    unittest.main()
