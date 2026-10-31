"""Real-PDF second-source fidelity audit, independent of draft author."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_microgen_offline_source_slide_draft import fixture
from microgen_offline_source_slide_draft import create_draft,sha
from microgen_serway_draft_audit import audit_serway_draft,SerwayDraftAuditError,main


class DraftAuditTests(unittest.TestCase):
    def setup_case(self, root):
        stage=fixture(root)
        with patch("microgen_offline_source_slide_draft._ensure_receipts"):
            create_draft(stage,root/"draft")
        return stage,root/"draft"

    def test_real_pdf_source_and_figure_and_si_warning_remain_unapproved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,draft=self.setup_case(root)
            old=(sha(stage/"source.pdf"),sha(stage/"Figure 1.1.png"))
            result=audit_serway_draft(stage,draft)
            self.assertEqual(result["slide_count"],8)
            self.assertEqual(result["source_pages_verified"],[1,2,3,4])
            self.assertGreater(result["source_text_characters"],0)
            self.assertTrue(result["historical_SI_warning_present"])
            self.assertTrue(result["embedded_figure_present"])
            self.assertFalse(result["end_to_end_lecture_complete"])
            self.assertFalse(result["full_narration_generated"])
            self.assertFalse(result["publication_allowed"])
            self.assertEqual((sha(stage/"source.pdf"),sha(stage/"Figure 1.1.png")),old)

    def test_draft_claiming_publication_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            stage,draft=self.setup_case(Path(td))
            receipt=draft/"slide_draft_receipt.json"
            data=json.loads(receipt.read_text())
            data["publication_allowed"]=True
            receipt.write_text(json.dumps(data))
            with self.assertRaises(SerwayDraftAuditError):
                audit_serway_draft(stage,draft)

    def test_modified_figure_or_source_pdf_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            stage,draft=self.setup_case(Path(td))
            with (stage/"Figure 1.1.png").open("ab") as f:f.write(b"drift")
            with self.assertRaises(SerwayDraftAuditError):
                audit_serway_draft(stage,draft)

    def test_missing_figure_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            stage,draft=self.setup_case(Path(td))
            (stage/"Figure 1.1.png").unlink()
            with self.assertRaises(SerwayDraftAuditError):
                audit_serway_draft(stage,draft)

    def test_existing_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage,draft=self.setup_case(root)
            output=root/"prior.json";output.write_text("protected")
            with self.assertRaises(SerwayDraftAuditError):
                main(["--stage",str(stage),"--draft",str(draft),
                      "--new-output",str(output)])
            self.assertEqual(output.read_text(),"protected")


if __name__=="__main__":
    unittest.main()
