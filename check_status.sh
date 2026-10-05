#!/usr/bin/env bash
set -euo pipefail
touch temp.log
# Iterate top-level directories whose names are all digits (e.g., ./1, ./23, ./0007)
while IFS= read -r -d '' intdir; do
  # Iterate immediate subdirectories under each integer directory (e.g., ./1/1.1, ./1/1.2)
  while IFS= read -r -d '' subdir; do
    # Check specifically for a file named 'slides.mp4' (case-sensitive)
    if [ -f "$subdir/slides.mp4" ]; then
      printf '%s\n' "$subdir/slides.mp4" >> temp.log
    else
      printf '%s No slides.mp4 found\n' "$subdir" >> temp.log
    fi
  done < <(find "$intdir" -mindepth 1 -maxdepth 1 -type d -print0)
done < <(find . -mindepth 1 -maxdepth 1 -type d \
         -regextype posix-extended -regex '.*/[0-9]+' -print0)

grep -vi 'problem' temp.log | sort  > status.log
rm -rf temp.log
cat status.log

