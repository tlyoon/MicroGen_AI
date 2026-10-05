#!/usr/bin/env python3
# -*- coding: utf-8 -*-

## Remove any line containing '\usepackage{siunitx}' from all *.tex files
## in the current directory.

import re
from pathlib import Path

# Regex to match an entire line that loads siunitx, e.g.
# \usepackage{siunitx}
#   \usepackage{siunitx}   % some comment
SIUNITX_LINE_RE = re.compile(
    r'^\s*\\usepackage\{siunitx\}\s*(%[^\n]*)?$',  # whole line
    re.MULTILINE,
)

def process_tex_file(path: Path) -> bool:
    
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        original = path.read_text(encoding="latin-1")

    new_text, n_subs = SIUNITX_LINE_RE.subn("", original)

    if n_subs > 0:
        # Also collapse any resulting empty lines (optional)
        # new_text = re.sub(r'\n\s*\n+', '\n\n', new_text)

        path.write_text(new_text, encoding="utf-8")
        print(f"[MODIFIED] {path.name} (removed {n_subs} siunitx line(s))")
        return True
    else:
        print(f"[SKIP] {path.name} (no siunitx line found)")
        return False


cwd = Path(".").resolve()
tex_files = sorted(cwd.glob("*.tex"))

if not tex_files:
    print("No .tex files found in current directory.")
#    return

print(f"Found {len(tex_files)} .tex file(s) in {cwd}")
modified_count = 0

for tex in tex_files:
    if process_tex_file(tex):
        modified_count += 1

print(f"Done. Modified {modified_count} file(s).")

