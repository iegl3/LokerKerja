import re, json, time
from typing import Any
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from . import config as ai_config
from .logutil import jlog

def _ms(t0): return f"{(time.perf_counter()-t0)*1000:.1f} ms"

PROMPT_JSON_STRICT = (
 "Ekstrak ke JSON. Jika tidak ada data biarkan null. Jangan menebak. HANYA JSON valid:\n"
 "{ name, contacts:{email,phone,location,links[]}, summary, skills[],"
 "  experience:[{company,role,start:\"YYYY-MM\"|null,end:\"YYYY-MM\"|null,duration_months:int|null,bullets[]}],"
 "  education:[{degree,school,start:\"YYYY-MM\"|null,end:\"YYYY-MM\"|null}], certs[] }"
)

def safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None

class ProviderDown(RuntimeError): ...

@retry(wait=wait_exponential(min=0.5, max=8), stop=stop_after_attempt(3),
       retry=retry_if_exception_type((TimeoutError, ProviderDown, RuntimeError)))
async def lunos_parse_async(text: str, req_id: str, model: str = ai_config.TEXT_MODEL, max_tokens: int = 1200):
    if ai_config.FAIL_LUNOS >= ai_config.CB_LIMIT:
        raise ProviderDown("AI circuit open")
    async with ai_config.SEM_LUNOS:
        t0 = time.perf_counter()
        msgs: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "Kamu HR yang mengekstrak CV ke JSON valid."},
            {"role": "user", "content": PROMPT_JSON_STRICT + "\n---\n" + text[:18000]},
        ]
        try:
            r = await ai_config.LUNOS.chat.completions.create(
                model=model, messages=msgs, temperature=0.1, max_tokens=max_tokens, timeout=90
            )
            body = (r.choices[0].message.content or "").strip()
            parsed = safe_json_loads(body)
            if parsed is None:
                fix = "Perbaiki ke JSON valid TANPA menambah data. Jawab hanya JSON.\n===\n" + body
                rr = await ai_config.LUNOS.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": fix}], temperature=0.0, max_tokens=800, timeout=60
                )
                parsed = safe_json_loads((rr.choices[0].message.content or "").strip()) or {"raw": body}
            ai_config.FAIL_LUNOS = 0
            return parsed, _ms(t0), getattr(r, "model", model)
        except Exception as e:
            ai_config.FAIL_LUNOS += 1
            jlog(event="ai_error", req_id=req_id, err=str(e), fail=ai_config.FAIL_LUNOS)
            raise

@retry(wait=wait_exponential(min=0.5, max=8), stop=stop_after_attempt(3),
       retry=retry_if_exception_type((TimeoutError, ProviderDown, RuntimeError)))
async def lunos_fill_dates_async(cv_text: str, profile: dict[str, Any], req_id: str, model: str = ai_config.TEXT_MODEL):
    miss = any((e.get("start") in (None, "") or e.get("end") in (None, "")) for e in profile.get("experience", []) or [])
    if not miss:
        return profile, "0.0 ms", model
    if ai_config.FAIL_LUNOS >= ai_config.CB_LIMIT:
        raise ProviderDown("AI circuit open")
    async with ai_config.SEM_LUNOS:
        t0 = time.perf_counter()
        ask = (
            "Lengkapi HANYA tanggal kosong (YYYY-MM) berdasarkan bukti TEKS. "
            "Jika tak ada bukti, biarkan null. Jangan ubah konten lain.\nTEKS:\n"
            + cv_text[:12000] + "\nJSON:\n" + json.dumps(profile, ensure_ascii=False)
        )
        try:
            r = await ai_config.LUNOS.chat.completions.create(
                model=model, messages=[{"role": "user", "content": ask}], temperature=0.0, max_tokens=600, timeout=60
            )
            txt = (r.choices[0].message.content or "").strip()
            fixed = safe_json_loads(txt) or profile
            ai_config.FAIL_LUNOS = 0
            return fixed, _ms(t0), getattr(r, "model", model)
        except Exception as e:
            ai_config.FAIL_LUNOS += 1
            jlog(event="ai_error", req_id=req_id, err=str(e), fail=ai_config.FAIL_LUNOS)
            raise
