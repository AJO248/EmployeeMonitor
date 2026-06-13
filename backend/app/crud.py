from typing import List

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .schemas import LogBatch
from .utils.normalizer import extract_domain


async def persist_log_batch(session: AsyncSession, batch: LogBatch) -> int:
    entries: List[dict] = []

    for entry in batch.entries:
        entries.append(
            {
                "device_id": entry.device_id or batch.device_id,
                "event_type": entry.type,
                "url": entry.url,
                "domain": extract_domain(entry.url) if entry.url else None,
                "title": entry.title,
                "app_name": entry.app_name,
                "event_ts": entry.timestamp,
            }
        )

    if not entries:
        return 0

    await session.execute(insert(models.LogEntry), entries)
    await session.commit()
    return len(entries)
