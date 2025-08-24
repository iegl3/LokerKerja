import time, asyncio
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from cv_handler.config import UNLI, SEM_UNLI, FAIL_UNLI, CB_LIMIT
from cv_handler.logutil import jlog

PROMPT_OCR = "Ekstrak seluruh teks CV berurutan dari header hingga footer. Jawab teks polos tanpa format."

class ProviderDown(RuntimeError): ...

def _ms(t0): return f"{(time.perf_counter()-t0)*1000:.1f} ms"

@retry(wait=wait_exponential(min=0.5, max=8), stop=stop_after_attempt(3),
       retry=retry_if_exception_type((TimeoutError, ProviderDown, RuntimeError)))
async def unli_vision_ocr_async(img_b64_list:list[str], req_id:str):
    global FAIL_UNLI
    if not UNLI: raise ProviderDown("UNLI_API_KEY not set (needed for OCR)")
    if FAIL_UNLI >= CB_LIMIT: raise ProviderDown("UNLI circuit open")
    async with SEM_UNLI:
        t0=time.perf_counter()
        content=[{"type":"image_url","image_url":{"url":u}} for u in img_b64_list]
        content.append({"type":"text","text":PROMPT_OCR})
        try:
            r=await UNLI.chat.completions.create(model="auto", messages=[{"role":"user","content":content}],
                                                 temperature=0.1, timeout=90)
            FAIL_UNLI=0
            return (r.choices[0].message.content or "").strip(), _ms(t0), getattr(r,"model","auto")
        except Exception as e:
            FAIL_UNLI += 1; jlog(event="unli_error", req_id=req_id, err=str(e), fail=FAIL_UNLI); raise