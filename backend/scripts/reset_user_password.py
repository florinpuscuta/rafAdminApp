"""One-off: reset a user's password by email (raw SQL to avoid ORM metadata imports)."""
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.security import hash_password


async def reset_password(email: str, new_password: str) -> None:
    engine = create_async_engine(settings.database_url)
    new_hash = hash_password(new_password)
    normalized_email = email.lower().strip()

    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE users SET password_hash = :h WHERE lower(email) = :e RETURNING id, active"),
            {"h": new_hash, "e": normalized_email},
        )
        row = result.first()
        if not row:
            print(f"User {email} not found")
            sys.exit(1)
        print(f"Password updated for {email} (id={row[0]}, active={row[1]})")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_user_password.py <email> <new_password>")
        sys.exit(2)
    asyncio.run(reset_password(sys.argv[1], sys.argv[2]))
