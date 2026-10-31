"""Voice-neutral production handoff does not certify an unfinished lecture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from microgen_offline_source_slide_draft import create_draft
from microgen_serway_draft_audit import audit_serway_draft
from microgen_serway_handoff import plan_serway_handoff,main,SerwayHandoffError
from test_microgen_offline_source_slide_draft import fixture


def setup(root):
    stage=fixture(root)
    with patch("microgen_offline_source_slide_draft._ensure_receipts"):
        create_draft(stage,root/"draft")
    evidence=root/"audited.json"
    evidence.write_text(json.dumps(audit_serway_draft(stage,root/"draft")))
    return stage,root/"draft",evidence


class SerwayHandoffTests(unittest.TestCase):
    def test_complete_eight_source_anchors_and_explicit_voice_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,draft,evidence=setup(root)
            work=plan_serway_handoff(stage,draft,evidence)
            self.assertEqual(work["slide_count"],8)
            self.assertEqual(len(work["narration_work_order"]),8)
            self.assertTrue(all(x["narration_text"] is None
                                for x in work["narration_work_order"]))
            self.assertTrue(work["narration_work_order"][3]["historical_SI_context_required"])
            self.assertTrue(work["narration_work_order"][4]["figure_academic_pixel_QA_required"])
            self.assertTrue(any(x["state"]=="UNCONFIGURED"
                for x in work["dependency_gates"]))
            self.assertFalse(work["formal_voice_authorized"])
            self.assertFalse(work["publication_allowed"])
            self.assertEqual(work["provider_calls"],0)

    def test_stale_or_forged_academic_acceptance_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,draft,evidence=setup(root)
            data=json.loads(evidence.read_text())
            data["publication_allowed"]=True
            evidence.write_text(json.dumps(data))
            with self.assertRaises(SerwayHandoffError):
                plan_serway_handoff(stage,draft,evidence)

    def test_modified_original_source_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,draft,evidence=setup(root)
            with (stage/"Figure 1.1.png").open("ab") as file:
                file.write(b"drift")
            with self.assertRaises(Exception):
                plan_serway_handoff(stage,draft,evidence)

    def test_cli_immutable_json_creation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,draft,evidence=setup(root)
            output=root/"handoff.json"
            self.assertEqual(main(["--stage",str(stage),"--draft",str(draft),
                "--audit",str(evidence),"--new-output",str(output)]),0)
            record=json.loads(output.read_text())
            self.assertFalse(record["generated_wavs"])
            self.assertFalse(record["generated_mp4s"])
            self.assertFalse(record["publication_allowed"])
            with self.assertRaises(SerwayHandoffError):
                main(["--stage",str(stage),"--draft",str(draft),
                    "--audit",str(evidence),"--new-output",str(output)])


if __name__=="__main__":
    unittest.main()
