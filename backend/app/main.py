from pathlib import Path

from . import models
from .config import settings
from .database import engine
from .database import AsyncSessionLocal
from .routes import analytics, auth, logs
from .security import bootstrap_admin
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="EM API")
app.include_router(logs.router)
app.include_router(auth.router)
app.include_router(analytics.router)

frontend_path = Path(__file__).resolve().parents[2] / "admin-frontend"
if frontend_path.exists():
    app.mount("/admin", StaticFiles(directory=frontend_path, html=True), name="admin")


@app.on_event("startup")
async def on_startup():
    if settings.create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await bootstrap_admin(session)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/admin/")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
