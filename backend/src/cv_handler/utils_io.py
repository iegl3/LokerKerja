import base64, hashlib, mimetypes
from pathlib import Path

def sha256_file(path:Path, chunk=1<<20):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(chunk), b""): h.update(b)
    return h.hexdigest()

def b64_image_bytes(bb:bytes, mime="image/png"):
    return f"data:{mime};base64,"+base64.b64encode(bb).decode()

def guess_mime(path:Path):
    return (mimetypes.guess_type(str(path))[0] or "application/octet-stream")