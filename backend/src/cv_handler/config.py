import os, asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
LUNOS_KEY = os.getenv("LUNOS_API_KEY")
UNLI_KEY  = os.getenv("UNLI_API_KEY")
APP_ID    = os.getenv("APP_ID", "lamarguard-backend")
if not LUNOS_KEY:
    raise ValueError("LUNOS_API_KEY not set")

LUNOS = AsyncOpenAI(api_key=LUNOS_KEY, base_url="https://api.lunos.tech/v1",
                    default_headers={"X-App-ID": APP_ID})
UNLI  = AsyncOpenAI(api_key=UNLI_KEY,  base_url="https://api.unli.dev/v1") if UNLI_KEY else None

# concurrency guards
SEM_LUNOS = asyncio.Semaphore(3)
SEM_UNLI  = asyncio.Semaphore(2)

# simple circuit breaker counters
FAIL_LUNOS = 0
FAIL_UNLI  = 0
CB_LIMIT   = 3
