# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

import functions
import time
start_time = time.time()
prefices = ["gen_md36","gen_json","gen_folders","gen_slides_video_in_subchapters","run_clean_leftover"]
#prefices = ["gen_slides_selenium"]

functions.prefices(prefices)

from pathlib import Path
local_time_struct = time.localtime(start_time)
formatted_time = time.strftime("%y:%m:%d:%H:%M:%S", local_time_struct)
here = Path(__file__).resolve().parent
this_file = Path(__file__)
fn = this_file.stem
elapsed = time.time() - start_time
print(f"{fn} elapsed time : {elapsed:.4f} seconds")
with open(f"{fn}.log", "w", encoding="utf-8") as log_file:    
    log_file.write(f"start_time (yy:mm:dd:hh:mm:ss): {formatted_time}\n")
    log_file.write(f"parent directory: {here}\n")
    log_file.write(f"prefices: {prefices}\n")
    log_file.write(f"{fn} elapsed time: {elapsed:.4f} seconds\n")

