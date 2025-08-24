import httpx
from settings import WA_BEARER_TOKEN, WA_PHONE_ID
import logging

logger = logging.getLogger(__name__)

async def send_text(to_wa: str, text: str):
    """Send WhatsApp text message"""
    async with httpx.AsyncClient(timeout=20) as cli:
        try:
            resp = await cli.post(
                f"https://graph.facebook.com/v20.0/{WA_PHONE_ID}/messages",
                headers={"Authorization": f"Bearer {WA_BEARER_TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to_wa,
                    "type": "text",
                    "text": {"body": text}
                }
            )
            resp.raise_for_status()
            logger.info(f"Message sent to {to_wa}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            raise
