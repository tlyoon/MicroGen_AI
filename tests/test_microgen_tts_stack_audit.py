import subprocess,tempfile,unittest
from pathlib import Path
from microgen_tts_stack_audit import audit_stack,StackAuditError

def git(repo,*cmd):
    p=subprocess.run(["git","-C",str(repo),*cmd],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout.strip()
def make(repo):
    git(repo,"init","-q")
    git(repo,"config","user.name","MicroGen CI")
    git(repo,"config","user.email","ci@example.invalid")
    (repo/"a.txt").write_text("first");git(repo,"add",".");git(repo,"commit","-qm","base")
    base=git(repo,"rev-parse","HEAD")
    (repo/"a.txt").write_text("second");git(repo,"commit","-qam","next")
    (repo/"b.txt").write_text("third");git(repo,"add",".");git(repo,"commit","-qm","next2")
    return base,git(repo,"rev-parse","HEAD")
class DraftStackAuditTests(unittest.TestCase):
 def test_two_linear_commits_pass(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   v=audit_stack(p,base,head)
   self.assertEqual(v["commit_count"],2)
   self.assertFalse(v["production_merge_performed"])
 def test_dirty_checkout_refused(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p);(p/"scratch.txt").write_text("dirty")
   with self.assertRaisesRegex(StackAuditError,"Dirty"):audit_stack(p,base,head)
 def test_reversed_ancestry_refused(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   with self.assertRaises(StackAuditError):audit_stack(p,head,base)
 def test_budget_is_enforced(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   with self.assertRaises(StackAuditError):audit_stack(p,base,head,max_commits=1)
