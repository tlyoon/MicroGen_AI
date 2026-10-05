import os, sys
#import subprocess, os, sys
from pathlib import Path
#from openai import OpenAI
#from langchain_community.document_loaders import PyPDFLoader
#import google.generativeai as genai
#from dotenv import load_dotenv
#from PyPDF2 import PdfReader, PdfWriter
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

def get_last_subchapters(json_file):
    """
    Reads a JSON file containing subchapter data and 
    returns a list of the last subchapter identifiers for each chapter.
    """
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    last_subchapters = {}
    for entry in data:
        title = entry.get("title", "")
        if "." in title:
            # Extract the subchapter identifier (e.g., "4.6")
            sub_id = title.split()[0]
            chapter = sub_id.split(".")[0]  # main chapter number
            # overwrite ensures we keep only the last seen subchapter per chapter
            last_subchapters[chapter] = sub_id

    # Return as a sorted list (by chapter number)
    return [last_subchapters[k] for k in sorted(last_subchapters.keys(), key=lambda x: int(x))]

### begin main ###
import shutil
origdir = os.getcwd()
json_path = "subchapter_index_physical.json"  # update path if needed
lastsubchaplist = get_last_subchapters(json_path)
lastsubchapdirs = [Path(os.path.join(i.split('.')[0], i)) for i in lastsubchaplist]
print('lastsubchapdirs are', [i.name for i in lastsubchapdirs])
print('')

import crop_pbset_fr_source
for subdir in lastsubchapdirs:
#    if subdir.is_dir() and subdir.name=='1.6':  ### for TS
    if subdir.is_dir():
        os.chdir(subdir)
        ## copy all files from origdir to subdir                
        # target is the current working directory
        target_dir = os.getcwd()        
        print(f"Copying files from {origdir} -> {target_dir}")        
        # ensure source exists
        if not os.path.isdir(origdir):
            raise FileNotFoundError(f"Source directory does not exist: {origdir}")
        
        # copy all files (not subfolders) from origdir to current directory
        for filename in os.listdir(origdir):
            src_file = os.path.join(origdir, filename)
            if os.path.isfile(src_file) and not filename=='source.pdf':   # only files
                shutil.copy2(src_file, target_dir)                
        print("✅ All files copied.")        
        if os.path.isfile("source.pdf"):
            print(f"✅ Found source.pdf in {os.getcwd()}")
            psdir = os.path.join(origdir,subdir.stem,"problems")            
            os.makedirs(psdir, exist_ok=True)
            
            # copy all files from origdir to psdir
            for filename in os.listdir(origdir):
                src_file = os.path.join(origdir, filename)
                if os.path.isfile(src_file) and not filename=='source.pdf':   # only files
                    shutil.copy2(src_file, psdir)                
            print(f"All files copied from {origdir} to {psdir}")                    
                        
            try:                                                
                crop_pbset_fr_source.main()
                pass
            except Exception as e:
                print(f"❌ Failed to extract problem set in {subdir}: {e}")
        else:
            print(f"⚠️ No source.pdf in {subdir}, skipping.")
        os.chdir(origdir)
        print('')  # blank line for readability
