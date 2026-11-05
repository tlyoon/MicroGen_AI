"""Regression: interrupted same-host Gemini worker must not block the lane.

Never remove tickets for a different PC, a live PID, an unknown process,
or an unaged ticket. Only move verified dead local entries to history.
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import gemini_lane


def ticket(queue,host,pid,token,age=150):
    created=datetime.now(timezone.utc)-timedelta(seconds=age)
    name=f"20261105T210000Z__{host}__{pid}__{token}.ticket.json"
    path=queue/name
    path.write_text(json.dumps({"host":host,"pid":pid,"token":token,
                                "created_utc":created.isoformat()}),
                    encoding="utf8")
    when=time.time()-age
    os.utime(path,(when,when))
    return path,created.timestamp()


class QueueRecoveryTests(unittest.TestCase):
    def setup(self,folder):
        with patch.dict(os.environ,{"MICROGEN_GEMINI_LANE_DIR":str(folder),
                                    "MICROGEN_GEMINI_LANE_STALE_SECONDS":"3600"}):
            lane=gemini_lane.GeminiLane(stage="slides")
        lane.host="Dell-115"
        lane.pid=9000
        lane.queue_dir.mkdir(parents=True)
        lane.history_dir.mkdir(parents=True)
        return lane

    def test_verified_dead_same_host_pid_archived_before_hour(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            old,_=ticket(lane.queue_dir,"Dell-115",5432,"a"*32)
            with patch("gemini_lane._windows_process_identity",
                       return_value=(False,None)):
                lane._remove_stale()
            self.assertFalse(old.exists())
            items=list(lane.history_dir.iterdir())
            self.assertEqual(len(items),1)
            self.assertIn("verified-local-orphan",items[0].name)

    def test_live_local_process_and_remote_host_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            live,issued=ticket(lane.queue_dir,"Dell-115",5432,"a"*32)
            other,_=ticket(lane.queue_dir,"Another-PC",4321,"b"*32)
            with patch("gemini_lane._windows_process_identity",
                       return_value=(True,issued-10)):
                lane._remove_stale()
            self.assertTrue(live.exists())
            self.assertTrue(other.exists())
            self.assertEqual(list(lane.history_dir.iterdir()),[])

    def test_pid_reuse_is_treated_as_stale_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            reused,issued=ticket(lane.queue_dir,"Dell-115",5432,"a"*32)
            with patch("gemini_lane._windows_process_identity",
                       return_value=(True,issued+30)):
                lane._remove_stale()
            self.assertFalse(reused.exists())
            self.assertEqual(len(list(lane.history_dir.iterdir())),1)

    def test_young_or_unknown_process_is_never_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            young,_=ticket(lane.queue_dir,"Dell-115",5432,"a"*32,age=20)
            uncertain,_=ticket(lane.queue_dir,"Dell-115",5433,"b"*32,age=150)
            with patch("gemini_lane._windows_process_identity",
                       return_value=None):
                lane._remove_stale()
            self.assertTrue(young.exists())
            self.assertTrue(uncertain.exists())
            self.assertEqual(list(lane.history_dir.iterdir()),[])

    def test_inconsistent_ticket_identity_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            bad,_=ticket(lane.queue_dir,"Dell-115",5432,"a"*32)
            data=json.loads(bad.read_text())
            data["pid"]=5342
            bad.write_text(json.dumps(data))
            os.utime(bad,(time.time()-150,)*2)
            with patch("gemini_lane._windows_process_identity",
                       return_value=(False,None)) as proc:
                lane._remove_stale()
            proc.assert_not_called()
            self.assertTrue(bad.exists())

    def test_stale_ticket_is_archived_not_deleted_even_if_unrelated(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=self.setup(Path(tmp))
            expired,_=ticket(lane.queue_dir,"Another-PC",4321,"b"*32,age=4000)
            lane._remove_stale()
            self.assertFalse(expired.exists())
            self.assertIn("stale",list(lane.history_dir.iterdir())[0].name)


if __name__=="__main__":
    unittest.main()
