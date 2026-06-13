import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./backend/dev.db")

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
