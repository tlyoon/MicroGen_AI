#! /bin/bash
find . -maxdepth 1 -type d -regextype posix-extended -regex './[0-9]+' -print0 | xargs -0 rm -rf
