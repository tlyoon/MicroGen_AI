#! /bin/bash

fn=$(basename "$(dirname "$PWD")")         # → parent-folder name
#echo $fn
zip "${fn}.zip"  *_mcq.xml
echo The following files
echo "$(ls *_mcq.xml)" 
echo 'has been zipped to' "${fn}".zip
