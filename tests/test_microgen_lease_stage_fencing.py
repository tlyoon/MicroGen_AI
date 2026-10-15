"""Offline fault-injection tests: a lost GCS lease fences active stage work."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import microgen_batch as batch
from microgen_ownership import LeaseLost


class LeaseProbe:
    def __init__(self, fail_on=None):
        self.calls = 0
        self.fail_on = fail_on

    def assert_held(self):
        self.calls += 1
        if self.fail_on is not None and self.calls >= self.fail_on:
            raise LeaseLost("Simulated lost distributed lease")


class LeaseStageFencingTests(unittest.TestCase):
    def setUp(self):
        self.windows_job_patches = []
        if __import__("os").name == "nt":
            for name, replacement in (
                ("_assign_windows_kill_job", mock.Mock(return_value=1234)),
                ("_close_windows_kill_job", mock.Mock()),
                ("_resume_windows_process", mock.Mock()),
            ):
                patcher = mock.patch.object(batch, name, replacement)
                patcher.start()
                self.addCleanup(patcher.stop)
                self.windows_job_patches.append(patcher)

    def test_active_leased_stage_terminated_when_ownership_lost(self):
        proc = mock.Mock()
        proc.wait.side_effect = subprocess.TimeoutExpired(["python", "stage.py"], 5)
        lease = LeaseProbe(fail_on=3)
        with tempfile.TemporaryDirectory() as tmp:
            log = (Path(tmp) / "log.txt").open("w")
            try:
                with mock.patch.object(batch.subprocess, "Popen", return_value=proc) as spawned, \
                     mock.patch.object(batch, "_terminate_stage_tree") as stopped:
                    with self.assertRaises(LeaseLost):
                        batch._run_leased_stage(
                            ["python", "stage.py"], cwd=Path(tmp),
                            log=log, lease=lease, timeout_seconds=60,
                        )
                    spawned.assert_called_once()
                    stopped.assert_called_once_with(proc)
            finally:
                log.close()

    def test_lease_must_remain_held_after_child_exits(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        lease = LeaseProbe(fail_on=3)
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "log.txt").open("w") as log, \
                 mock.patch.object(batch.subprocess, "Popen", return_value=proc), \
                 mock.patch.object(batch, "_terminate_stage_tree") as stopped:
                with self.assertRaises(LeaseLost):
                    batch._run_leased_stage(
                        ["python", "stage.py"], cwd=Path(tmp),
                        log=log, lease=lease, timeout_seconds=60,
                    )
                stopped.assert_called_once_with(proc)

    def test_healthy_lease_allows_success(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        lease = LeaseProbe()
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "log.txt").open("w") as log, \
                 mock.patch.object(batch.subprocess, "Popen", return_value=proc), \
                 mock.patch.object(batch, "_terminate_stage_tree") as stopped:
                self.assertEqual(
                    batch._run_leased_stage(
                        ["python", "stage.py"], cwd=Path(tmp),
                        log=log, lease=lease, timeout_seconds=60,
                    ), 0,
                )
                stopped.assert_not_called()
        self.assertGreaterEqual(lease.calls, 3)

    def test_single_pc_uses_existing_subprocess_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            with mock.patch.object(batch.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run, \
                 mock.patch.object(batch, "_run_leased_stage") as leased:
                batch.run_subprocess(
                    "python", "stage.py", stage, stage / "output.log",
                    "test", gemini_stage=False, retries=0,
                )
                run.assert_called_once()
                leased.assert_not_called()

    def test_lease_loss_interrupts_capacity_circuit_wait(self):
        with mock.patch.object(batch, "circuit_is_open", return_value=(True, {"type": "capacity"})), \
             mock.patch.object(batch.time, "sleep") as sleep:
            with self.assertRaises(LeaseLost):
                batch.wait_for_gemini_circuit(LeaseProbe(fail_on=1))
            sleep.assert_not_called()


    def test_expired_stage_deadline_terminates_tree(self):
        proc = mock.Mock()
        lease = LeaseProbe()
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "stage.log").open("w") as log, \
                 mock.patch.object(batch.subprocess, "Popen", return_value=proc), \
                 mock.patch.object(batch, "_terminate_stage_tree") as stopped:
                with self.assertRaises(subprocess.TimeoutExpired):
                    batch._run_leased_stage(
                        ["python", "stage.py"], cwd=Path(tmp),
                        log=log, lease=lease, timeout_seconds=-1,
                    )
                stopped.assert_called_once_with(proc)

    def test_missing_lease_before_start_never_spawns(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "stage.log").open("w") as log, \
                 mock.patch.object(batch.subprocess, "Popen") as launched:
                with self.assertRaises(LeaseLost):
                    batch._run_leased_stage(
                        ["python", "stage.py"], cwd=Path(tmp),
                        log=log, lease=LeaseProbe(fail_on=1),
                        timeout_seconds=60,
                    )
                launched.assert_not_called()


    def test_real_descendant_cannot_continue_after_lease_loss(self):
        """Integration check: terminate a live driver plus its child process."""
        # Use the real Windows Job Object here, not the unit-test mocks.
        for patcher in self.windows_job_patches:
            patcher.stop()
        import sys
        import time
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            marker = folder / "orphan-wrote.txt"
            parent = folder / "driver.py"
            child = folder / "child.py"
            ready = folder / "driver-ready.txt"
            child.write_text(
                "import time\nfrom pathlib import Path\n"
                f"time.sleep(10)\nPath({str(marker)!r}).write_text('escaped')\n",
                encoding="utf-8",
            )
            parent.write_text(
                "import subprocess,sys,time\nfrom pathlib import Path\n"
                f"subprocess.Popen([sys.executable,{str(child)!r}])\n"
                f"Path({str(ready)!r}).write_text('ready')\n"
                "time.sleep(40)\n", encoding="utf-8",
            )
            with (folder / "stage.log").open("w") as log:
                start = time.monotonic()
                with self.assertRaises(LeaseLost):
                    batch._run_leased_stage(
                        [sys.executable, str(parent)], cwd=folder,
                        log=log, lease=LeaseProbe(fail_on=3),
                        timeout_seconds=30,
                    )
                self.assertLess(time.monotonic() - start, 18)
                self.assertTrue(ready.exists(), "Driver never started its descendant")
            # If the child survives process-tree termination, it writes after
            # ten seconds. A little margin detects such a leaked descendant.
            time.sleep(7)
            self.assertFalse(marker.exists(), "Orphan child survived lease fencing")


if __name__ == "__main__":
    unittest.main()
