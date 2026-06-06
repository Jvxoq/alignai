"""
Session table DDL (run manually until migrations are added):

CREATE TABLE sessions (
    id          UUID PRIMARY KEY,
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, func, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    message_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


async def get_session(session_id: UUID) -> SessionRecord | None:
    async with async_session_factory() as db:
        result = await db.execute(select(SessionRecord).where(SessionRecord.id == session_id))
        return result.scalar_one_or_none()


async def upsert_session(session_id: UUID, message_count: int) -> SessionRecord:
    async with async_session_factory() as db:
        result = await db.execute(select(SessionRecord).where(SessionRecord.id == session_id))
        record = result.scalar_one_or_none()
        if record is None:
            record = SessionRecord(id=session_id, message_count=message_count)
            db.add(record)
        else:
            record.message_count = message_count
        await db.commit()
        await db.refresh(record)
        return record
