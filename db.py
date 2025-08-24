import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def init_pool(dsn: str):
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

def pool() -> asyncpg.Pool:
    assert _pool is not None, "DB pool not initialized"
    return _pool

async def dedupe_message(message_id: str, phone: str) -> bool:
    """
    Pokušaj upisa message_id u inbound_messages.
    Ako već postoji → vrati False (duplikat).
    """
    q = """
    INSERT INTO inbound_messages (message_id, phone_number)
    VALUES ($1, $2)
    ON CONFLICT (message_id) DO NOTHING
    RETURNING true
    """
    async with pool().acquire() as conn:
        return bool(await conn.fetchval(q, message_id, phone))

async def get_or_create_user(phone: str, name: Optional[str]) -> int:
    q_sel = "SELECT id FROM users WHERE phone_number = $1"
    q_ins = "INSERT INTO users (phone_number, user_name) VALUES ($1,$2) RETURNING id"
    async with pool().acquire() as conn:
        uid = await conn.fetchval(q_sel, phone)
        if uid:
            return uid
        return await conn.fetchval(q_ins, phone, name)

async def insert_food_item(
    user_id: int,
    name: str,
    qty_text: Optional[str],
    location: str,
    message_id: Optional[str],
    parsed_by: str,
) -> int:
    """
    Upis: tekstualna quantity (za UX), + normalizirani quantity_value/unit,
    + forenzika (message_id, parsed_by). 'consumed' default false.
    """
    import re
    qty_value, qty_unit = None, None
    if qty_text:
        m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Zčćšđž]+)?", qty_text)
        if m:
            qty_value = float(m.group(1).replace(",", ".")) if m.group(1) else None
            qty_unit = m.group(2).lower() if m.group(2) else None

    q = """
    INSERT INTO user_food_items
      (user_id, food_name, quantity, quantity_value, quantity_unit, location, consumed, message_id, parsed_by)
    VALUES ($1,$2,$3,$4,$5,$6,false,$7,$8)
    RETURNING id
    """
    async with pool().acquire() as conn:
        return await conn.fetchval(
            q, user_id, name, qty_text or "", qty_value, qty_unit, location, message_id, parsed_by
        )
