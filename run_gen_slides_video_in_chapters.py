# Assuming in current directory all chapter/subchapter/ directories have been populated with *.py and source.pdf file, launch this code execute run_gen_slides_video.py in all subchapter directories or in selected chapters or selected subchapters:

# It also assumes the existence of the folder at the same directory as this code, "template_v1". Files from template_v1 will be copied into chapter/subchapter/

import shutil, subprocess, sys
from pathlib import Path
import csv, os, re
import numpy as np
from pathlib import Path
import time
import glob

# stdout unicode safe
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')


base_dir = Path.cwd()
# --- auto-detect template folder matching "template_v*" ---
matches = sorted(glob.glob(str(base_dir / "llm_template_v*")))

if not matches:
    raise FileNotFoundError("❌ No directory matching pattern 'template_v*' found.")
template_dir = Path(matches[-1])  # pick the latest (alphabetically or numerically)
print(f"📦 Using template directory: {template_dir}\n")
##
##
llmtemplatedir = Path(template_dir)
loaded_subchapters=[]
origdir = Path('.')
dirs = np.sort([d for d in origdir.iterdir() if d.is_dir() and re.fullmatch(r'[1-9]\d*', d.name)])
dirs = sorted(dirs, key=lambda x: int(x.name))
for d in dirs:
        ##
        origdirr = Path(d)
        #dirs = np.sort([d for d in origdir.iterdir() if d.is_dir() and
        dirss = np.sort([dd for dd in origdirr.iterdir() if dd.is_dir()])
        for sd in dirss:
            if 'problems' in str(sd):
                #print(sd,'problems in it')
                pass
            else:                
                loaded_subchapters.append(sd)                
                #print(sd)                                
        #print('')
print("There are", len(loaded_subchapters), "subchapter directories")        
allsubchapters = [ i.name for i in loaded_subchapters ]
print('allsubchapters ', allsubchapters)
#print('loaded_subchapters ',loaded_subchapters)
     
### initialization: do not change ###
chapters=[];subchapters=[];
### initialization: do not change ###

### you can only select ONLY ONE OPTIONS (1,2 or 3) ###
#### option 1: define which subchapters you want #######
subchapters = ['9.1']

#### option 2: define which chapters you want #######
#chapters = ['5','6','7','8']

#### option 3: select all subchpaters #######
# subchapters = allsubchapters  ## all subchapters
### End of you can only select ONLY ONE OPTIONS (1,2 or 3) ###


### do not touch anything below ####
if chapters:
    print(f'chapters selected: {chapters}')
    subchapters = [ i for i in allsubchapters if i.split('.')[0] in chapters]

if not subchapters:
    print(f'subchapters list is not defined. To abort')
    sys.exit(0)
print('')    
print(f'subchapters to process: {subchapters}\n')


# --- helper to run a script and show its output, failing fast on error ---

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
        
### 1 ###
for i in loaded_subchapters:
    if i.is_dir():
        subchapter = i.name
        if subchapter in subchapters:            
            for f in llmtemplatedir.iterdir():
                if f.is_file():
                    shutil.copy2(f, i / f.name)
            print(f"Copied all files from {llmtemplatedir} into {i}")

            #1                        
            exepy1='run_gen_slides.py'
            print(f'To execute python {exepy1} in {str(i)}')
            run_py(exepy1, cwd=i)
            print('')
            
            #2
            exepy2='run_gen_video.py'  
            print(f'To execute python {exepy2} in {str(i)}')
            run_py(exepy2, cwd=i)
            print('')
