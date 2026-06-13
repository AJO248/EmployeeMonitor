import time
from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import settings


async def enforce_ingest_rate_limit(client_key: str, session: AsyncSession) -> None:
    now_ts = int(time.time())
    current_window = now_ts // 60

    # Clean up old entries (older than 2 minutes) to prevent table bloat
    await session.execute(
        delete(models.RateLimit).where(models.RateLimit.window_minute < current_window - 2)
    )

    # Query current window for this client
    statement = select(models.RateLimit).where(
        models.RateLimit.client_key == client_key,
        models.RateLimit.window_minute == current_window
    )
    result = await session.execute(statement)
    entry = result.scalar_one_or_none()

    if entry:
        if entry.request_count >= settings.ingest_rate_limit:
            await session.commit()
            raise HTTPException(status_code=429, detail="Ingestion rate limit exceeded")
        entry.request_count += 1
    else:
        entry = models.RateLimit(
            client_key=client_key,
            window_minute=current_window,
            request_count=1
        )
        session.add(entry)

    try:
        await session.commit()
    except Exception:
        # Handle compound PK duplicate inserts from concurrent processes
        await session.rollback()
        result = await session.execute(statement)
        entry = result.scalar_one_or_none()
        if entry:
            if entry.request_count >= settings.ingest_rate_limit:
                raise HTTPException(status_code=429, detail="Ingestion rate limit exceeded")
            entry.request_count += 1
            await session.commit()
        else:
            raise HTTPException(status_code=500, detail="Database rate limiting conflict")
