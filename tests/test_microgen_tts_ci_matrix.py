import unittest
from microgen_tts_ci_matrix import validate_ci_matrix,MatrixAuditError

def rows():
    return [{"name":f"unit ({os}, {py})","id":x+1,"status":"completed","conclusion":"success"}
       for x,(os,py) in enumerate((("windows-latest","3.11"),("windows-latest","3.12"),
                          ("ubuntu-latest","3.11"),("ubuntu-latest","3.12")))]
class MatrixTests(unittest.TestCase):
 def test_complete_all_green(self):
  report=validate_ci_matrix(rows())
  self.assertTrue(report["all_jobs_passed"])
  self.assertFalse(report["github_api_origin_authenticated_by_this_function"])
 def test_failed_job_disallows_green(self):
  a=rows();a[0]["conclusion"]="failure"
  self.assertIn(a[0]["name"],validate_ci_matrix(a)["blocking_job_names"])
 def test_pending_disallows_green(self):
  a=rows();a[0]["status"]="in_progress";a[0]["conclusion"]=None
  self.assertFalse(validate_ci_matrix(a)["all_jobs_passed"])
 def test_missing_duplicate_and_unknown_jobs_rejected(self):
  a=rows()
  for wrong in (a[:-1],a[:3]+[a[0]],a[:3]+[{**a[3],"name":"unit (macos-latest, 3.12)"}]):
   with self.assertRaises(MatrixAuditError):validate_ci_matrix(wrong)
