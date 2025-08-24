from pathlib import Path
import fitz  # pymupdf
from pdfminer.high_level import extract_text

def pdf_extract_text(path:Path)->str:
    try: return (extract_text(str(path)) or "").strip()
    except: return ""

def pdf_page_to_png_bytes(path:Path, page_index:int, scale:float=2.0)->bytes:
    doc=fitz.open(str(path))
    try:
        if page_index<0 or page_index>=len(doc): return b""
        pix=doc.load_page(page_index).get_pixmap(matrix=fitz.Matrix(scale,scale))
        return pix.tobytes("png")
    finally: doc.close()