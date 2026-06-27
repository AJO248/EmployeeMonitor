from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import settings
from .database import get_session

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": username, "exp": expires_at, "type": "admin"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def authenticate_admin(
    username: str, password: str, session: AsyncSession
) -> Optional[models.AdminUser]:
    result = await session.execute(
        select(models.AdminUser).where(
            models.AdminUser.username == username, models.AdminUser.is_active.is_(True)
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> models.AdminUser:
    token = credentials.credentials if credentials else request.cookies.get("cpam_access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "admin" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await session.execute(
        select(models.AdminUser).where(
            models.AdminUser.username == payload["sub"], models.AdminUser.is_active.is_(True)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Unknown admin")
    return user


async def bootstrap_admin(session: AsyncSession) -> None:
    result = await session.execute(
        select(models.AdminUser).where(
            models.AdminUser.username == settings.bootstrap_admin_username
        )
    )
    user = result.scalar_one_or_none()
    if user:
        if not verify_password(settings.bootstrap_admin_password, user.password_hash):
            user.password_hash = hash_password(settings.bootstrap_admin_password)
            await session.commit()
        return

    session.add(
        models.AdminUser(
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(settings.bootstrap_admin_password),
        )
    )
    await session.commit()
