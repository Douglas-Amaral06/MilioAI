import uuid
from unittest.mock import AsyncMock

import httpx
import pytest_asyncio
from sqlalchemy import delete

from app.auth.dependencies import Principal, current_user
from app.core.config import Settings
from app.db.models import User
from app.main import create_app


@pytest_asyncio.fixture
async def resources(tmp_path, monkeypatch):
    settings = Settings(storage_path=tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        monkeypatch.setattr(app.state.ollama, "operational_intent", AsyncMock(return_value="documental"))
        async with app.state.sessions() as session:
            user = User(identity=f"test:{uuid.uuid4()}", scopes=["test"])
            other = User(identity=f"test:{uuid.uuid4()}", scopes=[])
            session.add_all([user, other])
            await session.commit()
        principal = Principal(user.id, ("test",))
        app.dependency_overrides[current_user] = lambda: principal
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client, principal, Principal(other.id, ())
        async with app.state.sessions() as session:
            await session.execute(delete(User).where(User.id.in_([user.id, other.id])))
            await session.commit()
