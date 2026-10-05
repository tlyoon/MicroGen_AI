import os, re, shutil
import json
from PyPDF2 import PdfReader, PdfWriter
from pathlib import Path
import numpy as np

import sys, glob
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')


json_path = "subchapter_index_physical.json"
chapters = []
base_path = Path(".")  # change if needed
pattern = re.compile(r"^\d+$")  # directory name must be all digits
subchapters = []
for path in base_path.iterdir():
    if path.is_dir() and pattern.match(path.name):
        for path2 in path.iterdir():
            if os.path.isdir(str(path2)):                
                chapter= path2.parent.name
                chapters.append(chapter)                
chapters = list(set(chapters))
chapters = np.array(chapters)
dummy = np.sort(chapters.astype(int))
chapters = list(dummy)


### Option 1: To generate problem sets in all chapter/problems/ subdirectories. This is set as the default
#chapters = [ str(i) for i in chapters]
### end of Option 1


### Option 2: To generate problem set in a specified chapter/problems/; e.g., chapters = ['8', '9']. Using this option will overwrite Option 1
chapters = ['9']
### end of Option 2


### do not touch anything below this line ####
base_dir = Path.cwd()
# --- auto-detect template folder matching "template_v*" ---
matches = sorted(glob.glob(str(base_dir / "llm_template_v*")))  ### for selenium version, "template_v*"; for api version, "llm_template_v*"


if not matches:
    raise FileNotFoundError("❌ No directory matching pattern 'template_v*' found.")
template_dir = Path(matches[-1])  # pick the latest (alphabetically or numerically)
print(f"📦 Using template directory: {template_dir}\n")
#llmtemplatedir = Path(template_dir)
##

def run_py(script: str, cwd: Path, extra_env: dict | None = None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    # Force UTF-8 decoding and never crash on stray bytes
    res = subprocess.run(
        [sys.executable, script],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",   # or "backslashreplace" / "ignore"
        check=False
    )
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, file=sys.stderr, end="")
    if res.returncode != 0:
        raise RuntimeError(f"{script} failed with code {res.returncode}")


import sys, subprocess
for i in chapters:
    psdir = os.path.join(i,'problems')
    if os.path.isdir(psdir):        
        for filename in os.listdir(template_dir):
            src_file = os.path.join(template_dir, filename)
            if os.path.isfile(src_file):  # only files            
                shutil.copy2(src_file,psdir)
                #pass
        print(f"Copied all files from {template_dir} into {psdir}\n")
        #1
        exepy1='run_gen_problems_xml.py' 
        print(f'To execute python {exepy1} in {psdir}')
        run_py(exepy1, cwd=psdir)
        print('')
    
