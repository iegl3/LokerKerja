import asyncio, argparse, uuid
from pathlib import Path
from cv_handler.logutil import jlog
from cv_handler.reader import read_cv_async

def parse_args():
    ap=argparse.ArgumentParser(description="CV reader async (PDF/image→OCR via UNLI→JSON via LUNOS)")
    ap.add_argument("path")
    ap.add_argument("--pages", help="contoh: '1-3' atau '1,3'", default=None)
    ap.add_argument("--force-ocr", action="store_true")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--ttl-days", type=int, default=7)
    return ap.parse_args()

async def amain():
    a=parse_args()
    req_id=str(uuid.uuid4()); p=Path(a.path)
    jlog(event="cv_ingest_start", req_id=req_id, path=str(p), size=p.stat().st_size)
    prof, meta, flags = await read_cv_async(p, a.pages, a.force_ocr, a.max_pages, a.scale,
                                            cache=not a.no_cache, ttl_days=a.ttl_days, req_id=req_id)
    jlog(event="cv_ingest_done", req_id=req_id, meta=meta, cache=flags["from_cache"])
    import json
    print("== PROFILE =="); print(json.dumps(prof, ensure_ascii=False, indent=2))
    print("== META    ==", meta, "| cache:", flags["from_cache"])
    print("READY:", bool(prof.get('name')) and len(prof.get('skills',[]))>=5 and bool(prof.get('experience')))

if __name__=="__main__":
    asyncio.run(amain())