import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import persist_log_batch
from ..config import settings
from ..database import get_session
from ..rate_limit import enforce_ingest_rate_limit
from ..schemas import LogBatch
from ..security import bearer_scheme

router = APIRouter(prefix="/api/v1")


@router.post("/logs")
async def ingest(
    batch: LogBatch,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
):
    if not credentials or not secrets.compare_digest(
        credentials.credentials, settings.ingest_token
    ):
        raise HTTPException(status_code=401, detail="Invalid ingestion token")
    if not batch.entries:
        raise HTTPException(status_code=400, detail="No entries")

    client_key = batch.device_id or (request.client.host if request.client else "unknown")
    await enforce_ingest_rate_limit(client_key, session)

    try:
        count = await persist_log_batch(session, batch)
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Could not persist log batch")

    return {"status": "ok", "received": count}
