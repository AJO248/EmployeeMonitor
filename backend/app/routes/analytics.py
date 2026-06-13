from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_session
from ..schemas import DeviceSummary, UsageItem
from ..security import require_admin
from ..utils.productivity import classify_activity

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_admin)],
)

MAX_INTERVAL_SECONDS = 300
OFFLINE_AFTER_SECONDS = 180


def _usage_items(values: Dict[str, int], is_app: bool, limit: int = 10) -> List[UsageItem]:
    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
    items = []
    for name, seconds in ranked[:limit]:
        if is_app:
            classification = classify_activity(name, None)
        else:
            classification = classify_activity("chrome.exe", name)
        items.append(UsageItem(name=name, seconds=seconds, classification=classification))
    return items


def _summarize(entries: List[models.LogEntry]) -> List[DeviceSummary]:
    by_device: Dict[str, List[models.LogEntry]] = defaultdict(list)
    for entry in entries:
        by_device[entry.device_id or "unknown"].append(entry)

    summaries = []
    for device_id, device_entries in by_device.items():
        device_entries.sort(key=lambda entry: entry.event_ts)
        apps: Dict[str, int] = defaultdict(int)
        domains: Dict[str, int] = defaultdict(int)
        active_seconds = 0
        idle_seconds = 0
        productive_seconds = 0

        for index, entry in enumerate(device_entries):
            if index + 1 < len(device_entries):
                gap = max(0, (device_entries[index + 1].event_ts - entry.event_ts) // 1000)
                duration = min(gap, MAX_INTERVAL_SECONDS)
            else:
                duration = 0

            if entry.event_type.startswith("idle_") and entry.event_type != "idle_ended":
                if index + 1 < len(device_entries):
                    idle_seconds += max(
                        0, (device_entries[index + 1].event_ts - entry.event_ts) // 1000
                    )
                continue

            active_seconds += duration

            # Evaluate productivity for the active duration
            classification = classify_activity(entry.app_name, entry.domain)
            if classification == "productive":
                productive_seconds += duration

            if entry.app_name:
                apps[entry.app_name] += duration
            if entry.domain:
                domains[entry.domain] += duration

        latest = device_entries[-1]
        age_seconds = max(
            0, int(datetime.now(timezone.utc).timestamp()) - latest.event_ts // 1000
        )
        if age_seconds > OFFLINE_AFTER_SECONDS:
            status = "Offline"
        elif latest.event_type.startswith("idle_") and latest.event_type != "idle_ended":
            status = "Idle"
        else:
            status = "Active"

        prod_score = (
            round((productive_seconds / active_seconds) * 100, 1)
            if active_seconds > 0
            else 0.0
        )

        summaries.append(
            DeviceSummary(
                device_id=device_id,
                status=status,
                active_seconds=active_seconds,
                idle_seconds=idle_seconds,
                productivity_score=prod_score,
                top_apps=_usage_items(apps, is_app=True),
                top_domains=_usage_items(domains, is_app=False),
            )
        )
    return summaries


@router.get("/summary", response_model=List[DeviceSummary])
async def summary(
    device_id: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=24 * 31),
    session: AsyncSession = Depends(get_session),
):
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
    statement = select(models.LogEntry).where(models.LogEntry.event_ts >= since)
    if device_id:
        statement = statement.where(models.LogEntry.device_id == device_id)
    statement = statement.order_by(models.LogEntry.device_id, models.LogEntry.event_ts)
    result = await session.execute(statement)
    return _summarize(list(result.scalars()))
