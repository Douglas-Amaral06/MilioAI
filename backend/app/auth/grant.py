"""Administrative scope management. No public HTTP grant endpoint."""

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import User
from app.db.session import database


async def grant(identity: str, scopes: list[str]):
    engine, sessions = database(get_settings().database_url)
    try:
        async with sessions() as session:
            user = await session.scalar(select(User).where(User.identity == identity))
            if user is None:
                raise SystemExit("User must authenticate at least once before scope assignment")
            user.scopes = scopes
            await session.commit()
            print("Authorization scopes updated")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Replace trusted user scopes (administrative access required)"
    )
    parser.add_argument("--identity", required=True)
    parser.add_argument("--scope", action="append", default=[])
    args = parser.parse_args()
    asyncio.run(grant(args.identity, args.scope))
