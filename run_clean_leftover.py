# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

import os, glob, shutil, stat, time, sys, subprocess
from pathlib import Path

def _handle_remove_readonly(func, path, exc_info):
    # Clear read-only bit and try again
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass
    try:
        func(path)
    except PermissionError:
        # brief retry in case another process releases the handle
        time.sleep(0.2)
        func(path)

def safe_rmtree(p: Path):
    if sys.platform.startswith("win"):
        # Clear read-only attributes recursively (helps with OneDrive/Explorer locks)
        try:
            subprocess.run(['attrib', '-R', '/S', '/D', str(p / '*')], check=False, shell=True)
        except Exception:
            pass
    shutil.rmtree(p, onerror=_handle_remove_readonly)

# ---- your patterns ----
# slide*.wav and slide*.pdf are documented v7 final outputs and are intentionally retained.
pattern1 = []
pattern2 = []
pattern3 = [i for i in glob.glob('script_*.txt')]
items = (
    pattern1
    + [i for i in pattern2 if i != 'slides.pdf']
    + glob.glob('orig_script*.txt')
    + pattern3 
    #+ ['pages', 'crops']
)

#print(f'To remove {items}')

for item in items:
    p = Path(item)
    if p.is_file():
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)  # clear read-only if set
            p.unlink()
            print(f"Deleted file: {p}")
        except Exception as e:
            print(f"Could not delete file {p}: {e}")
    elif p.is_dir():
        try:
            safe_rmtree(p)
            print(f"Deleted folder: {p}")
        except Exception as e:
            print(f"Could not delete folder {p}: {e}")
    else:
        #print(f"Not found: {p}")
        pass

## clean up all temporary files ##
pattern = [p for p in glob.glob('*backup*') if not Path(p).name.startswith('_backup_before_pri_integration_')] + glob.glob('*raw*.xml') + glob.glob('*snapshots*') + ['section_content.txt'] + glob.glob('*TEMP*.mp4') + \
glob.glob('script_orig_*problemset*.xml') + glob.glob('script_orig_*problemset*.xml') + \
glob.glob('sanitized_*problemset*.xml')  + \
glob.glob('cleaned_*.tex') + \
glob.glob('script_orig_*.tex') + \
glob.glob('sanitized_*.tex') + \
glob.glob('*compile*.log') + \
glob.glob('*.aux') + \
glob.glob('*problemset.log') + \
glob.glob('*__error*') + \
glob.glob("*defective*") + \
glob.glob("orig_*") + \
[ i for i in glob.glob('slides.*') if i.split('.')[-1] not in ['mp4', 'pdf', 'tex']]

for path in pattern:
    if os.path.isfile(path):
        print(f"Deleted file: {path}")
        os.remove(path)
    elif os.path.isdir(path):
        print(f"Deleted folder: {path}")
        shutil.rmtree(path)
