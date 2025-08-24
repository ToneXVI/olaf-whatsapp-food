import hmac
import hashlib
import json
import time
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from openai import AsyncOpenAI
from contextlib import asynccontextmanager

from settings import *
from db import init_pool, dedupe_message, get_or_create_user, insert_food_item
from rules import parse as quick_parse
from wa import send_text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_pool(DB_URL)
    logger.info("Database pool initialized")
    yield
    # Shutdown
    logger.info("Shutting down")

# Create app
app = FastAPI(title="OLAF Core", lifespan=lifespan)
oai = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "time": time.time()}

# WhatsApp webhook verification (GET)
@app.get("/webhook")
async def verify(req: Request):
    """WhatsApp webhook verification endpoint"""
    q = dict(req.query_params)
    if q.get("hub.verify_token") == META_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(q.get("hub.challenge", ""))
    logger.warning("Invalid verify token")
    raise HTTPException(403, "Bad verify token")

# WhatsApp webhook handler (POST)
@app.post("/webhook")
async def inbound(req: Request, bg: BackgroundTasks):
    """Main webhook handler for incoming WhatsApp messages"""
    
    # HMAC validation
    body = await req.body()
    sig = req.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(META_APP_SECRET, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(sig, expected):
        logger.warning("Invalid webhook signature")
        raise HTTPException(403, "Invalid signature")

    # Parse webhook payload
    data = json.loads(body)
    try:
        value = data["entry"][0]["changes"][0]["value"]
        msg = value["messages"][0]
        wa_from = msg["from"]
        message_id = msg["id"]
        name = value["contacts"][0].get("profile", {}).get("name")
        phone_id = value["metadata"]["phone_number_id"]
    except (KeyError, IndexError) as e:
        logger.info(f"No message in webhook: {e}")
        return JSONResponse({"status": "ignored-no-message"})

    # Deduplicate
    if not await dedupe_message(message_id, wa_from):
        logger.info(f"Duplicate message: {message_id}")
        return JSONResponse({"status": "duplicate"})

    # Get/create user
    user_id = await get_or_create_user(wa_from, name)
    logger.info(f"Processing message from user {user_id} ({wa_from})")

    # Process in background
    bg.add_task(process_message, user_id, message_id, wa_from, msg, phone_id)
    
    # Quick ACK to WhatsApp
    return JSONResponse({"status": "ok"})

async def process_message(user_id: int, message_id: str, wa_from: str, msg: dict, phone_id: str):
    """Process message in background"""
    started = time.monotonic()
    
    # Extract text (or handle audio)
    text = msg.get("text", {}).get("body")
    
    if not text and msg.get("type") == "audio":
        # TODO: Download and transcribe audio
        await send_text(wa_from, "🎤 Primio sam audio, transkripcija uskoro...")
        return
    
    if not text:
        await send_text(wa_from, "❓ Nisam razumio poruku")
        return

    # Try rules-based parsing first
    qp = quick_parse(text)
    logger.info(f"Rules parse result: {qp}")
    
    # Handle query intent
    if qp["intent"] == "query":
        # TODO: Implement inventory query
        await send_text(wa_from, "📦 Radim popis tvoje hrane... (uskoro)")
        return
    
    # Handle add intent with high confidence
    if qp["intent"] == "add" and qp["food_name"] and qp["location"] and qp["confidence"] >= 0.8:
        await insert_food_item(
            user_id,
            qp["food_name"],
            qp["quantity"],
            qp["location"],
            message_id,
            "rules"
        )
        msg_text = f"✅ Dodano: {qp[\"quantity\"] or \"\"} {qp[\"food_name\"]} → {qp[\"location\"]}".strip()
        await send_text(wa_from, msg_text)
        logger.info(f"Added via rules: {msg_text}")
        return

    # Fallback to LLM for unclear messages
    if oai:
        try:
            resp = await oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Return ONLY JSON with keys: action, items[].name, items[].quantity, items[].location."},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=150
            )
            
            parsed = json.loads(resp.choices[0].message.content)
            logger.info(f"LLM parse result: {parsed}")
            
            if parsed.get("action") == "add" and parsed.get("items"):
                item = parsed["items"][0]
                await insert_food_item(
                    user_id,
                    item.get("name", "item"),
                    item.get("quantity", "unknown"),
                    item.get("location", "pantry"),
                    message_id,
                    "llm"
                )
                msg_text = f"✅ Dodano: {item.get(\"quantity\", \"\")} {item.get(\"name\", \"\")} → {item.get(\"location\", \"pantry\")}".strip()
                await send_text(wa_from, msg_text)
                logger.info(f"Added via LLM: {msg_text}")
            else:
                await send_text(wa_from, "❓ Molim te reci što točno i gdje (škrinja/hladnjak/ostava)?")
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            await send_text(wa_from, "⚠️ Greška u obradi. Pokušaj ponovo.")
    else:
        # No LLM available, ask for clarification
        await send_text(wa_from, "❓ Molim te budi precizniji: što dodaješ i gdje?")
    
    elapsed = time.monotonic() - started
    logger.info(f"Message processed in {elapsed:.2f}s")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
