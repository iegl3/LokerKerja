import os, asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

AI_KEY = os.getenv("AI_API_KEY") or os.getenv("9ROUTER_API_KEY") or os.getenv("LUNOS_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.9router.com/v1")
APP_ID = os.getenv("AI_APP_ID", os.getenv("APP_ID", "lokerkerja-backend"))
if not AI_KEY:
    raise ValueError("AI_API_KEY not set")

AI = AsyncOpenAI(
    api_key=AI_KEY,
    base_url=AI_BASE_URL,
    default_headers={
        "X-App-ID": APP_ID,
        "HTTP-Referer": os.getenv("APP_PUBLIC_URL", "https://lokerkerja.my.id"),
        "X-Title": "LokerKerja",
    },
)

# Backward-compatible aliases for old provider modules.
LUNOS = AI
UNLI = AI
TEXT_MODEL = os.getenv("AI_TEXT_MODEL", os.getenv("LUNOS_PRIMARY_MODEL", "openai/gpt-4o-mini"))
VISION_MODEL = os.getenv("AI_VISION_MODEL", "openai/gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", os.getenv("LUNOS_EMBEDDING_MODEL", "openai/text-embedding-3-small"))

# concurrency guards
SEM_LUNOS = asyncio.Semaphore(3)
SEM_UNLI = asyncio.Semaphore(2)

# simple circuit breaker counters
FAIL_LUNOS = 0
FAIL_UNLI = 0
CB_LIMIT = 3
