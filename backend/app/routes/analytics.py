from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_session
from ..schemas import DeviceSummary, UsageItem, DeviceTimelineEvent, DeviceTrend
from ..security import require_admin
from ..utils.productivity import classify_activity, BROWSER_APPS

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

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    summaries = []
    for device_id, device_entries in by_device.items():
        device_entries.sort(key=lambda entry: entry.event_ts)
        apps: Dict[str, int] = defaultdict(int)
        domains: Dict[str, int] = defaultdict(int)
        active_seconds = 0
        idle_seconds = 0
        productive_seconds = 0

        # Propagated state
        current_app = None
        current_domain = None

        for index, entry in enumerate(device_entries):
            # 1. Update propagated state based on the current event
            if entry.app_name:
                current_app = entry.app_name
                # If the app changed to a non-browser, clear the browser domain context
                if current_app.lower() not in BROWSER_APPS:
                    current_domain = None
            
            if entry.domain:
                current_domain = entry.domain
                # If we have a domain, ensure we are classified under a browser app
                if not current_app or current_app.lower() not in BROWSER_APPS:
                    current_app = "chrome.exe"

            # 2. Determine duration of this state interval
            if index + 1 < len(device_entries):
                gap = max(0, (device_entries[index + 1].event_ts - entry.event_ts) // 1000)
                duration = min(gap, MAX_INTERVAL_SECONDS)
            else:
                # Last event: count ongoing activity if active recently
                latest_ts = entry.event_ts
                age_sec = max(0, (now_ms - latest_ts) // 1000)
                if age_sec <= OFFLINE_AFTER_SECONDS:
                    duration = min(age_sec, MAX_INTERVAL_SECONDS)
                else:
                    duration = 0

            # 3. Process active vs. idle interval
            if entry.event_type.startswith("idle_") and entry.event_type != "idle_ended":
                idle_seconds += duration
                current_app = None
                current_domain = None
                continue

            active_seconds += duration

            # Evaluate productivity using propagated state
            classification = classify_activity(current_app, current_domain)
            if classification == "productive":
                productive_seconds += duration

            if current_app:
                apps[current_app] += duration
            if current_domain:
                domains[current_domain] += duration

        latest = device_entries[-1]
        age_seconds = max(
            0, now_ms // 1000 - latest.event_ts // 1000
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


@router.get("/timeline/{device_id}", response_model=List[DeviceTimelineEvent])
async def timeline(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=24 * 31),
    session: AsyncSession = Depends(get_session),
):
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    statement = select(models.LogEntry).where(
        models.LogEntry.device_id == device_id,
        models.LogEntry.event_ts >= since
    ).order_by(models.LogEntry.event_ts)
    
    result = await session.execute(statement)
    entries = list(result.scalars())
    
    events = []
    current_app = None
    current_domain = None
    
    for index, entry in enumerate(entries):
        if entry.app_name:
            current_app = entry.app_name
            if current_app.lower() not in BROWSER_APPS:
                current_domain = None
        if entry.domain:
            current_domain = entry.domain
            if not current_app or current_app.lower() not in BROWSER_APPS:
                current_app = "chrome.exe"
                
        if index + 1 < len(entries):
            gap = max(0, (entries[index + 1].event_ts - entry.event_ts) // 1000)
            duration = min(gap, MAX_INTERVAL_SECONDS)
        else:
            latest_ts = entry.event_ts
            age_sec = max(0, (now_ms - latest_ts) // 1000)
            if age_sec <= OFFLINE_AFTER_SECONDS:
                duration = min(age_sec, MAX_INTERVAL_SECONDS)
            else:
                duration = 0
                
        if duration > 0:
            if entry.event_type.startswith("idle_") and entry.event_type != "idle_ended":
                events.append(DeviceTimelineEvent(
                    timestamp=entry.event_ts,
                    duration_seconds=duration,
                    app_name=None,
                    domain=None,
                    classification="idle"
                ))
                current_app = None
                current_domain = None
            else:
                classification = classify_activity(current_app, current_domain)
                events.append(DeviceTimelineEvent(
                    timestamp=entry.event_ts,
                    duration_seconds=duration,
                    app_name=current_app,
                    domain=current_domain,
                    classification=classification
                ))
                
    return events


@router.get("/trends", response_model=List[DeviceTrend])
async def trends(
    device_id: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=24 * 31),
    session: AsyncSession = Depends(get_session),
):
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    statement = select(models.LogEntry).where(models.LogEntry.event_ts >= since)
    if device_id:
        statement = statement.where(models.LogEntry.device_id == device_id)
    statement = statement.order_by(models.LogEntry.device_id, models.LogEntry.event_ts)
    result = await session.execute(statement)
    entries = list(result.scalars())
    
    by_device: Dict[str, List[models.LogEntry]] = defaultdict(list)
    for entry in entries:
        by_device[entry.device_id or "unknown"].append(entry)
        
    trends_by_hour: Dict[int, DeviceTrend] = {}
    
    for d_id, device_entries in by_device.items():
        current_app = None
        current_domain = None
        
        for index, entry in enumerate(device_entries):
            if entry.app_name:
                current_app = entry.app_name
                if current_app.lower() not in BROWSER_APPS:
                    current_domain = None
            if entry.domain:
                current_domain = entry.domain
                if not current_app or current_app.lower() not in BROWSER_APPS:
                    current_app = "chrome.exe"
                    
            if index + 1 < len(device_entries):
                gap = max(0, (device_entries[index + 1].event_ts - entry.event_ts) // 1000)
                duration = min(gap, MAX_INTERVAL_SECONDS)
            else:
                age_sec = max(0, (now_ms - entry.event_ts) // 1000)
                if age_sec <= OFFLINE_AFTER_SECONDS:
                    duration = min(age_sec, MAX_INTERVAL_SECONDS)
                else:
                    duration = 0
                    
            if duration > 0:
                # Group by hour
                dt = datetime.fromtimestamp(entry.event_ts / 1000, tz=timezone.utc)
                hour_dt = dt.replace(minute=0, second=0, microsecond=0)
                hour_ts = int(hour_dt.timestamp() * 1000)
                
                if hour_ts not in trends_by_hour:
                    trends_by_hour[hour_ts] = DeviceTrend(
                        hour_timestamp=hour_ts,
                        productive_seconds=0,
                        unproductive_seconds=0,
                        neutral_seconds=0,
                        idle_seconds=0
                    )
                
                if entry.event_type.startswith("idle_") and entry.event_type != "idle_ended":
                    trends_by_hour[hour_ts].idle_seconds += duration
                    current_app = None
                    current_domain = None
                else:
                    classification = classify_activity(current_app, current_domain)
                    if classification == "productive":
                        trends_by_hour[hour_ts].productive_seconds += duration
                    elif classification == "unproductive":
                        trends_by_hour[hour_ts].unproductive_seconds += duration
                    else:
                        trends_by_hour[hour_ts].neutral_seconds += duration
                        
    return sorted(trends_by_hour.values(), key=lambda t: t.hour_timestamp)
