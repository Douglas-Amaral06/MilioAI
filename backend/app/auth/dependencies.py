import asyncio
import secrets
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import AppError
from app.db.models import User

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: uuid.UUID
    scopes: tuple[str, ...]


async def current_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    settings = request.app.state.settings
    if not credentials:
        raise AppError(401, "unauthenticated", "Entre para acessar suas conversas.")
    if settings.auth_mode == "development":
        if not secrets.compare_digest(credentials.credentials, settings.dev_auth_token):
            raise AppError(401, "unauthenticated", "Credencial inválida.")
        identity = "development:local-user"
    else:
        try:
            key = await asyncio.to_thread(
                request.app.state.jwks.get_signing_key_from_jwt, credentials.credentials
            )
            claims = jwt.decode(
                credentials.credentials,
                key.key,
                algorithms=["RS256", "ES256"],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = str(uuid.UUID(claims["sub"]))
            identity = f"{settings.jwt_issuer}:{subject}"
        except (jwt.PyJWTError, ValueError, KeyError):
            raise AppError(401, "unauthenticated", "Sessão inválida ou expirada.") from None
    async with request.app.state.sessions() as session:
        await session.execute(
            insert(User)
            .values(identity=identity, scopes=[])
            .on_conflict_do_nothing(index_elements=[User.identity])
        )
        await session.commit()
        user = (await session.scalars(select(User).where(User.identity == identity))).one()
        # Scopes are server-managed, never taken from editable user_metadata or client headers.
        return Principal(
            user.id,
            tuple(
                ["test", *settings.dev_document_scopes, *user.scopes]
                if settings.auth_mode == "development"
                else user.scopes
            ),
        )
