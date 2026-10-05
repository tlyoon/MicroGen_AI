#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
from pathlib import Path
import glob

base_dir = Path.cwd()

# --- auto-detect template folder matching "llm_template_v*" ---
matches = sorted(glob.glob(str(base_dir / "llm_template_v*")))
if not matches:
    raise FileNotFoundError("❌ No directory matching pattern 'llm_template_v*' found.")
template_dir = Path(matches[-1])  # pick the latest (alphabetically or numerically)
print(f"📦 Using template directory: {template_dir}")

# --- copy files into all subdirectories of integer-named directories ---
for d in sorted(base_dir.iterdir()):
    if d.is_dir() and d.name.isdigit():  # only integer-named dirs
        print(f"\n📁 Processing main directory: {d}")
        for sub in sorted(d.iterdir()):
            if sub.is_dir():
                print(f"➡️  Copying templates/* into: {sub}")
                for file in template_dir.iterdir():
                    if file.is_file():
                        dest = sub / file.name
                        shutil.copy2(file, dest)
                        #print(f"   cp {file} {dest}")
        #print(f'files from {template_dir} are copied to sub-directory {dest}')
print("\n✅ All template files copied successfully.")

