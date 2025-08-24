import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
META_APP_SECRET = os.environ["META_APP_SECRET"].encode()
META_VERIFY_TOKEN = os.environ["META_VERIFY_TOKEN"]
WA_BEARER_TOKEN = os.environ["WA_BEARER_TOKEN"]
WA_PHONE_ID = os.environ["WA_PHONE_ID"]
DEFAULT_TZ = os.environ.get("DEFAULT_TZ", "Europe/Zagreb")
