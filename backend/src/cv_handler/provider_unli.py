import time
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
)
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from . import config as ai_config
from .logutil import jlog

PROMPT_OCR = "Ekstrak seluruh teks CV berurutan dari header hingga footer. Jawab teks polos tanpa format."

class ProviderDown(RuntimeError): ...

def _ms(t0): return f"{(time.perf_counter()-t0)*1000:.1f} ms"

@retry(wait=wait_exponential(min=0.5, max=8), stop=stop_after_attempt(3),
       retry=retry_if_exception_type((TimeoutError, ProviderDown, RuntimeError)))
async def unli_vision_ocr_async(img_b64_list: list[str], req_id: str):
    if not ai_config.UNLI:
        raise ProviderDown("AI_API_KEY not set (needed for OCR)")
    if ai_config.FAIL_UNLI >= ai_config.CB_LIMIT:
        raise ProviderDown("AI vision circuit open")
    async with ai_config.SEM_UNLI:
        t0 = time.perf_counter()
        content: list[ChatCompletionContentPartParam] = []
        for u in img_b64_list:
            image_part: ChatCompletionContentPartImageParam = {"type": "image_url", "image_url": {"url": u}}
            content.append(image_part)
        text_part: ChatCompletionContentPartTextParam = {"type": "text", "text": PROMPT_OCR}
        content.append(text_part)
        try:
            user_message: ChatCompletionUserMessageParam = {"role": "user", "content": content}
            messages: list[ChatCompletionMessageParam] = [user_message]
            r = await ai_config.UNLI.chat.completions.create(
                model=ai_config.VISION_MODEL, messages=messages, temperature=0.1, timeout=90
            )
            ai_config.FAIL_UNLI = 0
            return (r.choices[0].message.content or "").strip(), _ms(t0), getattr(r, "model", ai_config.VISION_MODEL)
        except Exception as e:
            ai_config.FAIL_UNLI += 1
            jlog(event="ai_vision_error", req_id=req_id, err=str(e), fail=ai_config.FAIL_UNLI)
            raise
