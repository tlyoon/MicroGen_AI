import tempfile
import unittest
from pathlib import Path

import microgen_batch


class BatchCheckpointTests(unittest.TestCase):
    def test_invalidate_from_preserves_earlier_stages(self):
        cp = {"completed": {name: "done" for name in microgen_batch.STAGES}}
        microgen_batch.invalidate_from(cp, "narration")
        self.assertIn("slides", cp["completed"])
        self.assertNotIn("narration", cp["completed"])
        self.assertNotIn("video", cp["completed"])

    def test_published_validator_requires_three_final_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / "stage"
            dest = root / "dest"
            stage.mkdir()
            dest.mkdir()
            for name in ("slides.pdf", "script.txt", "slides.mp4"):
                (dest / name).write_bytes(b"x")
            self.assertTrue(microgen_batch.stage_valid(stage, "published", dest))
            (dest / "script.txt").unlink()
            self.assertFalse(microgen_batch.stage_valid(stage, "published", dest))


if __name__ == "__main__":
    unittest.main()
