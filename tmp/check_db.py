
import asyncio
from app.db.session import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        res = await conn.execute(text('SELECT id, key_prefix, is_active FROM tenant_api_keys'))
        rows = res.fetchall()
        print(f"Found {len(rows)} keys")
        for row in rows:
            print(f"ID: {row[0]}, Prefix: {row[1]}, Active: {row[2]}")

if __name__ == "__main__":
    asyncio.run(check())
