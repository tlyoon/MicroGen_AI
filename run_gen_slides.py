import os
import functions
import time
start_time = time.time()

prefices = ["abs_figures_merged","gen_slides"]
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
