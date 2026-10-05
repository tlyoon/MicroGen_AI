# -*- coding: utf-8 -*

# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
# This file is part of the MicroGen_AI package.
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

import re
import shutil 
#import contractions

import re

# Fix mispronunciation of physics variables attached to numbers (e.g., 3g -> 3 G, 2L -> 2 L)
# This prevents "3g" being read as "3 grams"
def fix_physics_variables(match):
    num = match.group(1)
    var = match.group(2).upper() # Force to uppercase for letter pronunciation
    return f"{num} {var}"


def normalize_scientific_text(text):
    # 1. Expand English contractions
    #text = contractions.fix(text)

    # 2. Abbreviation replacements with space-separated uppercase letters (no dots)
    abbreviation_map = {                
        #'Inc.': 'I N C', 
        #'Ltd.': 'L T D',
        #'No.': 'N O',                 
        #'et al.': 'E T A L',
        #'ibid.': 'I B I D', 
        #'op. cit.': 'O P C I T',        
        #'loc. cit.': 'L O C C I T',
        ##'Dept.': 'D E P T', 
        #'Univ.': 'U N I V', 
        #'Vol.': 'V O L', 
        
        #'Trans.': 'T R A N S', 
        'Ser.': 'S E R', 
        'Bk.': 'B K',
        'Fig.': 'F I G',         
        'Ref.': 'R E F', 
        'e.g.': 'E G', 
        'i.e.': 'I E',
        'etc.': 'E T C', 
        'U.S.': 'U S', 
        'U.K.': 'U K', 
    }
    for abbr in sorted(abbreviation_map, key=len, reverse=True):
        pattern = r'\b' + re.escape(abbr) + r'\b'
        text = re.sub(pattern, abbreviation_map[abbr], text)

    # Original two-letter US state abbreviations
    us_states = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
    'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
    'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'
    ]

    # Step 1: Create lowercase, space-separated, quoted form: ' c o ', etc.
    us_state_map = {
    abbr: f"' {abbr[0].lower()} {abbr[1].lower()} '"
    for abbr in us_states}

    # Step 2: Replace spaced versions (e.g., "C O" → "' c o '")
    for abbr in us_states:
        spaced_pattern = rf"\b{abbr[0]}\s+{abbr[1]}\b"
        replacement = f"' {abbr[0].lower()} {abbr[1].lower()} '"
        text = re.sub(spaced_pattern, replacement, text)

    # Step 3: Replace compact versions (e.g., "CO" → "' c o '")
    for abbr in sorted(us_state_map, key=len, reverse=True):
        pattern = rf"\b{abbr}\b"
        text = re.sub(pattern, us_state_map[abbr], text)

    # 4. Chemical elements
    elements = [
    'H','B','C','N','O','F','Mg','Al','P','S','Cl','Ar','K','Sc','Ti',
    'V','Cr','Mn','Ni','Zn','Br','Kr','Rb','Sr','Y','Zr','Nb',
    'Tc','Ru','Rh','Pd','Ag','Cd','Sn','Sb','Cs','Pr','Nd','Pm','Sm', 'Eu','Gd','Tb','Dy','Er','Tm','Yb','Hf','W','Re','Os','Ir','Pt','Hg','Tl','Pb','Rn','Fr','Ac','Th','U','Np','Cm','Bk','Cf','Es','Fm','Md','Lr','Rf','Db','Sg','Bh','Hs','Mt','Ds','Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og',  
]
    element_map = {el: ' '.join(el) for el in elements}
    #element_map['U'] = "'u'"
    #element_map['V'] = "'v'"
    
    for el in sorted(element_map, key=len, reverse=True):
        pattern = r'\b' + re.escape(el) + r'\b'
        text = re.sub(pattern, element_map[el], text)

    # Replace underscores with a space (e.g., omega_f -> omega f, v_f -> v f)
    text = re.sub(r'([a-zA-Z0-9])_([a-zA-Z0-9])', r'\1 \2', text)    
    text = re.sub(r'\bU(?=\W|$)', "'u'", text)    
    text = re.sub(r'\bo(?=\W|$)', "' o '", text)
    text = re.sub(r'\bO(?=\W|$)', "' o '", text)
    text = re.sub(r'\bDr(?=\W|$)', "'D' 'r'", text)
    text = re.sub(r'\bDR(?=\W|$)', "'D' 'R'", text)
    text = re.sub(r'\bMr(?=\W|$)', "'M' 'R'", text)
    text = re.sub(r'\bMR(?=\W|$)', "'M' 'R'", text)
    text = re.sub(r'\bMs(?=\W|$)', "'M' 'S'", text)
    text = re.sub(r'\bMrs(?=\W|$)', "'M' 'R' 'S'", text)
    text = re.sub(r'\bST(?=\W|$)', "'S' 'T'", text)
    text = re.sub(r'\bSt(?=\W|$)', "'S' 'T'", text)
    text = re.sub(r'\bEq(?=\W|$)', "'E' 'Q'", text)
    text = re.sub(r'\bEQ(?=\W|$)', "'E' 'Q'", text)
    text = re.sub(r'\bvs(?=\W|$)', "'v' 'S'", text)
    text = re.sub(r'\bVs(?=\W|$)', "'v' 'S'", text)
    text = re.sub(r'\bVS(?=\W|$)', "'v' 'S'", text)
    #text = re.sub(r'\bp(?=\W|$)', "'P' ", text)
    #text = re.sub(r'\bpp(?=\W|$)', "'P' 'P'", text)
    
    text = re.sub(r'\bp\b', "P", text)
    
    text = re.sub(r'\bCo(?=\W|$)', "' c ' ' o '", text)
    text = re.sub(r'\bco(?=\W|$)', "' c ' ' o '", text)
    text = re.sub(r'\bca(?=\W|$)', "' c ' 'A'", text)
    text = re.sub(r'\bcf(?=\W|$)', "' c ' 'F'", text)
    text = re.sub(r'\bop(?=\W|$)', "' o ' 'P'", text)
    text = re.sub(r'\bed(?=\W|$)', "'E' 'D'", text)
    text = re.sub(r'\beds(?=\W|$)', "'E' 'D' 'S' ", text)
    text = re.sub(r'\bRev(?=\W|$)', "'E' 'E' 'v' ", text)
    text = re.sub(r'\bch(?=\W|$)', "'C' 'H' ", text)
    text = re.sub(r'\bCH(?=\W|$)', "'C' 'H' ", text)
    text = re.sub(r'\bCh(?=\W|$)', "'C' 'H' ", text)
    text = re.sub(r'\bst(?=\W|$)', "' s ' ' t ' ", text)
    text = re.sub(r'\bnd(?=\W|$)', "' n ' ' d ' ", text)
    text = re.sub(r'\brd(?=\W|$)', "' r ' ' d ' ", text)
    text = re.sub(r'\b(v)\.(?=\W|$)', r"'\1'.", text, flags=re.IGNORECASE)  ## v. --> 'v'.; V. --> 'V'.
    #text = re.sub(r"\b[vV]([0-9]+(?:\.[0-9]+)?)(?=\W|$)", r"'v' \1", text)
    text = re.sub('\u2013', '-', text)
    text = re.sub(r"(?<!\*)[\u0080-\uFFFF](?!\*)", "", text)
    text = re.sub(r"[ˋ’ʿʻ]", "`", text)
    text = re.sub(r"`", "'", text)
    text = re.sub(r'\bI\s+n\b', 'in', text)
    text = re.sub(r'\bA\s+s\b', 'as', text)
    text = text.replace("''", "'")
    text = re.sub(r'(?<!\w)k(?!\w)', 'K', text)  # e.g., "k," "k." "(k)" -> "K," "K." "(K)"
    text = re.sub(r'(?<!\w)y(?!\w)', 'Y', text)  # e.g., "y," "y?" "[y]" -> "Y," "Y?" "[Y]"    
    text = re.sub(r'(?i)\bdee\b', 'd', text)   ### dee --> d    
    # space out differentials: dy, du, dx, dt, dv, dr, ...
    text = re.sub(r'(?i)\bd([xuytvr])\b', r'd \1', text)    
    text = re.sub(r'(?<!\w)a\.(?=\s|$)', "A.", text, flags=re.IGNORECASE)  ## "a." --> A.    
    text = re.sub(r'\bdu\.(?=\W|$)', r"'d u'.", text)  # 1) du.  -->  'd u'.
    text = re.sub(r'\bdu\b', r"'d u'", text)  # 2) du   -->  'd u'
    text = re.sub(r'\s*/\s*', ' over ', text) # Replace every "/" (with or without surrounding spaces) by " over "
    text = re.sub(r' {2,}', ' ', text).strip()  # (Optional) tidy up accidental double spaces that might result
    text = re.sub(r"(?<!['\"])\bY\b\s*,", "'Y',", text)  # Replace: Y,  -->  'Y',
    
    # Replace number + m with number + M (e.g., 3.55m -> 3.55M)
    text = re.sub(r'(\d+(?:\.\d+)?)(\s*)m\b', r'\1\2M', text)
    
    # Fix 'cause' being read as 'because'
    text = re.sub(r'\bcause\b', "kawse", text)
    
    # Fix subscript pronunciation (e.g., a sub i -> A sub i)
    # TTS engines almost always read uppercase single letters as names (Ay, Bee, Em)
    text = re.sub(r'\b([a-zA-Z])\s+sub\s+([a-zA-Z0-9])\b', lambda m: f"{m.group(1).upper()} sub {m.group(2)}", text)

    # Specific fix for "a" before math variables or descriptors
    # This prevents "a times b" from sounding like "uh times b"
    text = re.sub(r'\ba\b(?=\s+(times|plus|minus|over|sub|equals))', 'A', text)    
        
    # Matches a digit followed by g or L (case insensitive for the letters)
    text = re.sub(r'(\d+)([gL])\b', fix_physics_variables, text)
    
    # Add this inside normalize_scientific_text to handle standalone g
    text = re.sub(r'(?<!\w)g(?!\w)', 'G', text)    
        
    # Ensure standalone r is read as a letter name, even near punctuation
    text = re.sub(r'(?<!\w)r(?!\w)', 'R', text)
    
    # To handle standalone v (e.g., velocity v)
    #text = re.sub(r'(?<!\w)v(?!\w)', "'v'", text, flags=re.IGNORECASE)
    
    #Replacement 'V': This changes the lowercase v to a capital V.
    text = re.sub(r'\bv\b', 'V', text)
            
    # Force standalone m or M to be read as a letter name by wrapping in quotes
    text = re.sub(r'(?<!\w)m(?!\w)', "'M'", text, flags=re.IGNORECASE)
    
    # Robustly replace all hyphens between alphanumeric characters or quotes
# using lookarounds to avoid character consumption issues.
    text = re.sub(r"(?<=['a-zA-Z0-9])-(?=['a-zA-Z0-9])", " ", text)
    
    # Clean up double single-quotes (e.g., ''M'' -> 'M')
    text = text.replace("''", "'")
    
    # Ensure standalone a is read as a letter name (Ay) instead of an article (uh)
    #text = re.sub(r'(?<!\w)a(?!\w)', 'A', text)
    text = re.sub(r'(?<!\w)a(?!\w)(?!\s+t\b)', 'A', text)
    
    # forces to ensure "letter" pronunciation, add a rule specifically for 'c.'.
    text = re.sub(r'(?<!\w)c\.(?=\s|$)', "C.", text, flags=re.IGNORECASE)
    
    # Fix "A t " occurrences 
    text = re.sub(r'\bA\s+t\b', 'At', text)
    
    # Separate letters from numbers (e.g., v2 -> v 2, y1 -> y 1)
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    
    # Protect standalone variables from Roman numeral interpretation
    for var in ['V', 'X', 'I']:
        text = re.sub(rf'\b{var}\b', var.lower(), text)
    
    #Quote all standalone single-letter words ONLY at sentence boundaries    
    text = re.sub(
    r'\b([A-Za-z])\.(?=\s+[A-Z])',
    lambda m: f"'{m.group(1).upper()}'.",
    text
    )
    
    #v. --> 'V' .
    text = re.sub(r'\bv\.(?=\s|$)', "'V' .", text, flags=re.IGNORECASE)    
    #v2, v10, V3 --> 'V' 2 / 'V' 10 / 'V' 3
    text = re.sub(r'\b[vV](\d+)\b', r"'V' \1", text)    
    #standalone v --> 'V'
    text = re.sub(r'\bv\b', "'V'", text, flags=re.IGNORECASE)
    
    # Replace calculus differentials (e.g. dy → d 'y')
    for var in ['x','y','z','v','r','s','t','a','b','c','e','i','u']:
        pattern = rf'\bd{var}(?=\W|$)'
        text = re.sub(pattern, f"d '{var}'", text)    
    
    
    ###### ---> fixes to be added here <--- ##############
    #Replace standalone 'u' and 'U' --> 'u'
    text = re.sub(r'(?<![\w\'"])([uU])(?![\w\'"])', r"'u'", text)    
    ###### ---> end of fixes to be added here <--- ##############
    
    return text

# === Read from script.txt, process, write to script_cleaned.txt ===
input_file = 'script.txt'
backup_file = 'orig_script.txt'
# Backup original
shutil.copyfile(input_file, backup_file)

# Read input
import chardet

with open('script.txt', 'rb') as f:
    raw_data = f.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']

with open('script.txt', 'r', encoding=encoding) as f:
    content = f.read()
    
#with open(input_file, 'r', encoding='utf-8') as f:
#    content = f.read()

# Normalize text
cleaned = normalize_scientific_text(content)

output_file = 'script.txt'
# Write output
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(cleaned)

#scriptfile = 'script.txt'
#normalize_scientific_text(scriptfile)
from pathlib import Path
def ensure_double_asterisk_blocks(script_file="script.txt", out_file=None):
    """
    Ensure each Slide block in script.txt is bounded by ** ... **.
    If already bounded, leave unchanged.
    """

    p = Path(script_file)
    text = p.read_text(encoding="utf-8").strip()

    # Split blocks by blank lines
    blocks = re.split(r'\n\s*\n', text)

    fixed_blocks = []

    for block in blocks:
        block = block.strip()

        # ignore empty
        if not block:
            continue

        # already formatted
        if block.startswith("**Slide") and block.endswith("**"):
            fixed_blocks.append(block)
            continue

        # match slide header
        if re.match(r"Slide\s+\d+\s+\[[^\]]+\]:", block):

            # remove any existing stray asterisks
            block = block.strip("*").strip()

            # add wrappers
            block = f"**{block}**"

        fixed_blocks.append(block)

    fixed_text = "\n\n".join(fixed_blocks) + "\n"

    if out_file is None:
        p.write_text(fixed_text, encoding="utf-8")
    else:
        Path(out_file).write_text(fixed_text, encoding="utf-8")

    return fixed_text
scriptfile = 'script.txt'
ensure_double_asterisk_blocks(scriptfile)