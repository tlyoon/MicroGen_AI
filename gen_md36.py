import torch
#import re
#import json
import PyPDF2
from pathlib import Path
#from PyPDF2 import PdfReader, PdfWriter 
#from dotenv import load_dotenv
#from openai import OpenAI
#import google.generativeai as genai
import sys
import logging
import time
import pymupdf  # PyMuPDF
import shutil
from multiprocessing import get_context
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

def extract_pages(pdf_path, start_page, end_page, output_filename):
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pdf_writer = PyPDF2.PdfWriter()
            for page_num in range(start_page - 1, end_page):
                try:
                    page = pdf_reader.pages[page_num]
                    pdf_writer.add_page(page)
                except IndexError:
                    print(f"Warning: Page {page_num + 1} out of range. Skipping.")
            with open(output_filename, 'wb') as output_file:
                pdf_writer.write(output_file)
        print(f"Pages {start_page}-{end_page} extracted successfully to {output_filename}")
    except FileNotFoundError:
        print(f"Error: File not found: {pdf_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def split_pdf_into_chunks(pdf_path, output_dir, n_chunks):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total_pages = doc.page_count
    pages_per_chunk = (total_pages + n_chunks - 1) // n_chunks
    chunk_paths = []
    for i in range(n_chunks):
        start_page = i * pages_per_chunk
        end_page = min(start_page + pages_per_chunk, total_pages)
        if start_page >= end_page:
            break
        chunk_path = output_dir / f"chunk_{i+1}.pdf"
        chunk_doc = pymupdf.open()
        for page_num in range(start_page, end_page):
            chunk_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        chunk_doc.save(chunk_path)
        chunk_paths.append(chunk_path)
    return chunk_paths

def convert_pdf_to_md(args):
    chunk_path, output_dir = args
    output_dir = Path(output_dir)
    chunk_index = chunk_path.stem.split('_')[-1]
    md_path = output_dir / f"chunk_{chunk_index}.md"
    options = PdfPipelineOptions(
        images_scale=1.0,
        generate_page_images=False,
        generate_picture_images=False,
        format_hints={"no_ocr": True, "no_tables": True, "no_figures": True},
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(chunk_path)
    result.document.save_as_markdown(md_path, image_mode=ImageRefMode.REFERENCED)
    return md_path

def stitch_md_chunks(md_paths, output_path):
    with open(output_path, "w", encoding="utf-8") as outfile:
        for md_file in sorted(md_paths, key=lambda x: int(x.stem.split('_')[-1])):
            with open(md_file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read() + "\n\n")

#if __name__ == "__main__":
start_time = time.time()
pdf_path = "source.pdf"
start_page = 1
end_page = 36
output_filename = f"{start_page}_{end_page}.pdf"
extract_pages(pdf_path, start_page, end_page, output_filename)

INPUT_PDF = output_filename
OUTPUT_DIR = Path(".")
final_md = "source.md"


if torch.cuda.is_available():
    print("CUDA is available! PyTorch can use your GPU.")
    print(f"GPU Name: {torch.cuda.get_device_name(0)}")
    NUM_CHUNKS = 4

    CHUNK_DIR = Path("pdf_chunks")
    chunk_paths = split_pdf_into_chunks(INPUT_PDF, CHUNK_DIR, NUM_CHUNKS)

    ctx = get_context("spawn")
    with ctx.Pool(processes=NUM_CHUNKS) as pool:
        md_paths = pool.map(convert_pdf_to_md, [(path, OUTPUT_DIR) for path in chunk_paths])
    stitch_md_chunks(md_paths, final_md)

else:
    print("CUDA is NOT available. Falling back to single-pass Markdown conversion...")
    options = PdfPipelineOptions(
        images_scale=1.0,
        generate_page_images=False,
        generate_picture_images=False,
        format_hints={"no_ocr": True, "no_tables": True, "no_figures": True},
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(INPUT_PDF)
    result.document.save_as_markdown(final_md, image_mode=ImageRefMode.REFERENCED)

logging.info(f"✅ Done. {output_filename} has been converted to: {final_md}")
logging.info(f"⏱️ Total time: {time.time() - start_time:.2f} seconds.")