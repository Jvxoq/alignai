from datetime import datetime
from functools import lru_cache
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, select, text, update, delete
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@lru_cache
def _get_engine():
    settings = get_settings()
    if not settings.POSTGRES_URL:
        raise RuntimeError("POSTGRES_URL is not configured")
    return create_async_engine(
        settings.POSTGRES_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"timeout": 10},
    )


@lru_cache
def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = _get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_user_by_email(email: str) -> UserRecord | None:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(select(UserRecord).where(UserRecord.email == email))
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: UUID) -> UserRecord | None:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(select(UserRecord).where(UserRecord.id == user_id))
        return result.scalar_one_or_none()


async def create_user(email: str, hashed_password: str) -> UserRecord:
    factory = _get_session_factory()
    async with factory() as db:
        user = UserRecord(email=email, hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def get_session_with_owner(session_id: UUID, user_id: UUID) -> SessionRecord | None:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(SessionRecord).where(
                SessionRecord.id == session_id,
                SessionRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def create_session(user_id: UUID) -> SessionRecord:
    factory = _get_session_factory()
    async with factory() as db:
        session = SessionRecord(user_id=user_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


async def get_sessions_for_user(user_id: UUID, limit: int = 50, offset: int = 0) -> list[SessionRecord]:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(SessionRecord)
            .where(SessionRecord.user_id == user_id)
            .order_by(SessionRecord.last_active_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


async def count_sessions_for_user(user_id: UUID) -> int:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(func.count()).select_from(SessionRecord).where(SessionRecord.user_id == user_id)
        )
        return result.scalar() or 0


async def create_session_if_under_limit(user_id: UUID, limit: int) -> SessionRecord | None:
    """Counts and inserts in the same transaction, holding a per-user advisory
    lock so two concurrent requests can't both pass the count check before
    either commits (a plain count-then-insert has a race here)."""
    factory = _get_session_factory()
    async with factory() as db:
        lock_stmt = text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)").bindparams(key=str(user_id))
        await db.execute(lock_stmt)

        result = await db.execute(
            select(func.count()).select_from(SessionRecord).where(SessionRecord.user_id == user_id)
        )
        if (result.scalar() or 0) >= limit:
            return None

        session = SessionRecord(user_id=user_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


async def increment_message_count(session_id: UUID, user_id: UUID) -> SessionRecord | None:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(
            update(SessionRecord)
            .where(
                SessionRecord.id == session_id,
                SessionRecord.user_id == user_id,
            )
            .values(
                message_count=SessionRecord.message_count + 1,
                last_active_at=func.now(),
            )
            .returning(SessionRecord)
        )
        await db.commit()
        return result.scalar_one_or_none()


async def update_session_title(session_id: UUID, user_id: UUID, title: str) -> SessionRecord | None:
    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(SessionRecord).where(
                SessionRecord.id == session_id,
                SessionRecord.user_id == user_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.title = title
        await db.commit()
        await db.refresh(record)
        return record


async def delete_session(session_id: UUID, user_id: UUID) -> bool:
    factory = _get_session_factory()
    async with factory() as db:
        cursor = cast(CursorResult[Any], await db.execute(
            delete(SessionRecord).where(
                SessionRecord.id == session_id,
                SessionRecord.user_id == user_id,
            )
        ))
        await db.commit()
        return cursor.rowcount > 0


async def delete_user(user_id: UUID) -> bool:
    factory = _get_session_factory()
    async with factory() as db:
        cursor = cast(CursorResult[Any], await db.execute(delete(UserRecord).where(UserRecord.id == user_id)))
        await db.commit()
        return cursor.rowcount > 0
