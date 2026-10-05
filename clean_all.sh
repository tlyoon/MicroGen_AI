#! /bin/bash

rm -rf slide* script.txt orig_script.txt defective_slides_oai.tex *.png pages/ crops/ 
rm -rf 1_20.pdf 1_30.pdf source.md subchapter_index_physical.json chunk_* pdf_chunkschunk_* pdf_chunks nohup.out script*.txt
rm -rf *.xml *.tex *problemset*.txt section_content.txt *.log
rm -rf rf *__snapshots
find . -maxdepth 1 -type f -name "*.pdf" ! -name "source.pdf" -exec rm -f {} +
# Get current directory
base_dir=$(pwd)
# Loop through all items in the current directory
for entry in "$base_dir"/*; do
  if [ -d "$entry" ]; then
    dirname=$(basename "$entry")
    if [[ "$dirname" =~ ^[0-9]+$ ]]; then
      echo "🗑️ Removing folder: $entry"
      rm -rf "$entry"
    fi
  fi
done










































