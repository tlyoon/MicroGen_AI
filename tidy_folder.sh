#!/bin/bash

shopt -s extglob nullglob

echo "🧹 Cleaning current directory: $(pwd)"
mkdir -p storage

# List files to be moved (excluding folders)
echo "🔍 Listing files to be moved from current directory:"
for file in *; do
    if [[ -f "$file" && ! "$file" =~ ^(script.txt|slides_gemini\..*|slides.mp4|.*\.png|source.pdf|Section_.*\.tex|Section_.*\.pdf)$ ]]; then
        echo "  - Moving: $file"
        mv -- "$file" storage/
    fi
done

echo "✅ Files moved to ./storage/"
echo ""

# Descend into two-level subdirectories
for dir in */*/; do
    [ -d "$dir" ] || continue
    echo "📂 Processing subdirectory: $dir"
    (
        cd "$dir" || exit
        shopt -s extglob nullglob

        echo "  🧹 Cleaning directory: $(pwd)"
        mkdir -p storage

        echo "  🔍 Listing files to be moved:"
        moved=false
        for file in *; do
            if [[ ! "$file" =~ ^(script.txt|slides_gemini\..*|slides.mp4|.*\.png|source.pdf|Section_.*\.tex|Section_.*\.pdf)$ ]]; then
                echo "    - Moving: $file"
                moved=true
            fi
        done

        # Perform the move
        mv -- !(@(script.txt|slides_gemini.@(*)|slides.mp4|*.png|source.pdf|Section_*.tex|*.xml)) storage/ 2>/dev/null

        if [[ "$moved" == true ]]; then
            echo "  ✅ Files moved to ./storage/"
        else
            echo "  ℹ️  No files needed to be moved."
        fi
        echo ""
    )
done

echo "✅ All directories processed."
