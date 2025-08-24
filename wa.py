import httpx
import logging
from settings import WA_BEARER_TOKEN, WA_PHONE_ID

logger = logging.getLogger(__name__)

async def send_text(to_wa: str, text: str):
    if not WA_BEARER_TOKEN or not WA_PHONE_ID:
        logger.warning("WA creds missing; skipping send_text")
        return
    async with httpx.AsyncClient(timeout=20) as cli:
        resp = await cli.post(
            f"https://graph.facebook.com/v20.0/{WA_PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {WA_BEARER_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_wa,
                "type": "text",
                "text": {"body": text},
            },
        )
        resp.raise_for_status()
