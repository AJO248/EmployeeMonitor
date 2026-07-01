from typing import List, Optional

from pydantic import BaseModel


class LogEntry(BaseModel):
    type: str
    timestamp: int
    url: Optional[str] = None
    title: Optional[str] = None
    app_name: Optional[str] = None
    device_id: Optional[str] = None


class LogBatch(BaseModel):
    device_id: Optional[str] = None
    entries: List[LogEntry]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsageItem(BaseModel):
    name: str
    seconds: int
    classification: str = "neutral"


class DeviceSummary(BaseModel):
    device_id: str
    status: str
    active_seconds: int
    idle_seconds: int
    productivity_score: float = 0.0
    top_apps: List[UsageItem]
    top_domains: List[UsageItem]


class DeviceTimelineEvent(BaseModel):
    timestamp: int
    duration_seconds: int
    app_name: Optional[str] = None
    domain: Optional[str] = None
    classification: str


class DeviceTrend(BaseModel):
    hour_timestamp: int
    productive_seconds: int
    unproductive_seconds: int
    neutral_seconds: int
    idle_seconds: int
