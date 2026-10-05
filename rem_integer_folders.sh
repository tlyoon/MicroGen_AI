#! /bin/bash


# Preview
for d in */; do n="${d%/}"; [[ "$n" =~ ^[0-9]+$ ]] && echo "Would remove: $d"; done
# Delete
for d in */; do n="${d%/}"; [[ "$n" =~ ^[0-9]+$ ]] && rm -rf -- "$d"; done

