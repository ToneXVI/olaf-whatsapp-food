import os
from dotenv import load_dotenv

load_dotenv()

def _must_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

DB_URL = _must_env("DATABASE_URL")
META_APP_SECRET = _must_env("META_APP_SECRET").encode()  # bytes for HMAC
META_VERIFY_TOKEN = _must_env("META_VERIFY_TOKEN")
DEFAULT_TZ = os.environ.get("DEFAULT_TZ", "Europe/Zagreb")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WA_BEARER_TOKEN = os.environ.get("WA_BEARER_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
