###############################################
"""
merge_lettered_figs.py

Scan current (or given) directory for PNGs like:
  'Figure 7.1a.png', 'Figure 7.1B.png', 'Figure 7.1c.PNG'
Group files that differ only by a single trailing letter right before the extension,
and merge each group horizontally into a single PNG named by the common stem:
  -> 'Figure 7.1.png'

Robustness:
- Case-insensitive on both the trailing letter and file extension.
- Accepts number patterns like 7.1a, 21-5b, 3-10.2C (i.e., digits separated by '.' or '-').
- Only merges when at least two lettered variants exist.
- Preserves the first-seen group's stem formatting (spacing/case) for the output name.
- Handles images with different heights by aligning to top and padding white below.
- Supports RGBA input (outputs RGB on white background).

Usage:
  python merge_lettered_figs.py
  python merge_lettered_figs.py --dir /path/to/dir --remove 0
"""

#from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image
except ImportError:
    raise SystemExit("This script requires Pillow. Install with: pip install pillow")


# Regex:
#   - Capture a stem that ends with a number token, where a number token is \d+(?:[.-]\d+)*
#   - Followed immediately by a single alphabetic letter (the variant)
#   - Followed by .png (any case)
# Examples matched:
#   "Figure 7.1a.png"             stem="Figure 7.1", letter="a"
#   "Figure 21-5B.PNG"            stem="Figure 21-5", letter="B"
#   "Some Name 3-10.2c.png"       stem="Some Name 3-10.2", letter="c"
'''
LETTERED_RE = re.compile(
    r"^(?P<stem>.*?\b[0-9]+(?:[.\-][0-9]+)*)"
    r"(?P<letter>[a-z])"
    r"\.png$",
    re.IGNORECASE,
)
'''

#   "Some Name 3-10.2c.png"       stem="Some Name 3-10.2", letter="c"
#   "Figure 7.7 a.png"            stem="Figure 7.7", letter="a"
#   "Figure 7.7_b.png"            stem="Figure 7.7", letter="b"
LETTERED_RE = re.compile(
    r"^(?P<stem>.*?\b[0-9]+(?:[.\-][0-9]+)*)"
    r"[ _]*"                                 # <-- ADDED: Match optional space/underscore
    r"(?P<letter>[a-z])"
    r"\.png$",
    re.IGNORECASE,
)


def find_lettered_groups(root: Path) -> Dict[str, List[Tuple[Path, str, str]]]:
    """
    Return a mapping: key = normalized stem (lowercased, single spaces),
    value = list of tuples (path, original_stem, letter_lower).
    We normalize the key for grouping; we keep the first original stem to name the output.
    """
    groups: Dict[str, List[Tuple[Path, str, str]]] = {}
    for p in root.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".png":
            continue

        m = LETTERED_RE.match(p.name)
        if not m:
            continue

        orig_stem = m.group("stem")
        letter = m.group("letter").lower()

        # Build a normalized grouping key (case/space-insensitive)
        norm_key = re.sub(r"\s+", " ", orig_stem.strip().lower())

        groups.setdefault(norm_key, []).append((p, orig_stem, letter))

    # Keep only those with at least two variants (a/b/...)
    groups = {k: v for k, v in groups.items() if len(v) >= 2}
    return groups


def open_image_rgb(path: Path) -> Image.Image:
    """Open an image, convert to RGB (white background if source has alpha)."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    elif im.mode != "RGB":
        return im.convert("RGB")
    return im


def merge_horizontally(images: List[Image.Image]) -> Image.Image:
    """Merge a list of PIL Images horizontally, top-aligned, padding shorter images with white."""
    if not images:
        raise ValueError("No images to merge")
    heights = [im.size[1] for im in images]
    widths = [im.size[0] for im in images]
    max_h = max(heights)
    total_w = sum(widths)

    canvas = Image.new("RGB", (total_w, max_h), (255, 255, 255))
    x = 0
    for im in images:
        canvas.paste(im, (x, 0))
        x += im.size[0]
    return canvas

def main():
    ap = argparse.ArgumentParser(description="Merge letter-suffixed PNG figure variants horizontally.")
    ap.add_argument("--dir", default=".", help="Directory to scan (default: current directory)")
    ap.add_argument("--remove", type=int, default=0, choices=[0, 1],
                    help="If 1, remove the component lettered files after merging (default: 0)")
    args = ap.parse_args()
    
    root = Path(args.dir).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    
    groups = find_lettered_groups(root)
    if not groups:
        print(f"[INFO] No mergeable lettered groups found in: {root}")
        #return
    
    print(f"[INFO] Found {len(groups)} group(s) to merge.")
    
    for norm_key, items in groups.items():
        # Sort components by letter (a, b, c, ...)
        items.sort(key=lambda t: t[2])  # t[2] is letter_lower
    
        # Use the first-seen original stem to name the output (preserves original spacing/case)
        _, original_stem_for_name, _ = items[0]
        # Normalize spaces around the stem for cleaner output
        output_stem = re.sub(r"\s+", " ", original_stem_for_name.strip())
    
        output_path = root / f"{output_stem}.png"
    
        # Load images in order
        ims = []
        ordered_files = []
        for path, _stem, _letter in items:
            try:
                im = open_image_rgb(path)
                ims.append(im)
                ordered_files.append(path)
            except Exception as e:
                print(f"[WARN] Skipping {path.name}: {e}")
    
        if len(ims) < 2:
            print(f"[INFO] Group '{output_stem}': fewer than 2 valid images after loading, skipping.")
            continue
    
        merged = merge_horizontally(ims)
        merged.save(output_path)
        for im in ims:
            im.close()
    
        print(f"[OK]  Merged {len(ordered_files)} file(s) → {output_path.name}")
    
        if args.remove == 1:
            for p in ordered_files:
                try:
                    p.unlink()
                except Exception as e:
                    print(f"[WARN] Could not remove {p.name}: {e}")
if __name__ == "__main__":
    main()