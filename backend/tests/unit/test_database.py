from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.infrastructure import database
from app.infrastructure.database import (
    SessionRecord,
    UserRecord,
    count_sessions_for_user,
    create_session,
    create_user,
    delete_session,
    delete_user,
    get_session,
    get_session_with_owner,
    get_sessions_for_user,
    get_user_by_email,
    get_user_by_id,
    increment_message_count,
    update_session_title,
)


class FakeResult:
    def __init__(self, scalar=None, scalars_list=None, rowcount=0):
        self._scalar = scalar
        self._scalars_list = scalars_list if scalars_list is not None else []
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars_list)


class FakeSession:
    def __init__(self, result=None):
        self.result = result if result is not None else FakeResult()
        self.executed_statements = []
        self.added = []
        self.committed = False
        self.refreshed = []

    async def execute(self, stmt):
        self.executed_statements.append(stmt)
        return self.result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_factory(fake_session: FakeSession):
    """_get_session_factory() returns a callable; calling it yields the async-context session."""
    return patch.object(database, "_get_session_factory", return_value=lambda: fake_session)


class TestGetEngine:
    def test_raises_when_postgres_url_missing(self):
        database._get_engine.cache_clear()
        with patch.object(database, "get_settings", return_value=SimpleNamespace(POSTGRES_URL="")):
            with pytest.raises(RuntimeError, match="not configured"):
                database._get_engine()
        database._get_engine.cache_clear()

    def test_builds_engine_when_postgres_url_present(self):
        database._get_engine.cache_clear()
        settings = SimpleNamespace(POSTGRES_URL="postgresql+asyncpg://user:pw@localhost:5432/db")
        with patch.object(database, "get_settings", return_value=settings):
            engine = database._get_engine()
        assert engine is not None
        database._get_engine.cache_clear()


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_found(self):
        user = UserRecord(email="a@b.com", hashed_password="hash")
        fake = FakeSession(result=FakeResult(scalar=user))
        with _patch_factory(fake):
            result = await get_user_by_email("a@b.com")
        assert result is user
        assert "users.email" in str(fake.executed_statements[0])

    @pytest.mark.asyncio
    async def test_not_found(self):
        fake = FakeSession(result=FakeResult(scalar=None))
        with _patch_factory(fake):
            result = await get_user_by_email("missing@b.com")
        assert result is None


class TestGetUserById:
    @pytest.mark.asyncio
    async def test_found(self):
        user_id = uuid4()
        user = UserRecord(id=user_id, email="a@b.com", hashed_password="hash")
        fake = FakeSession(result=FakeResult(scalar=user))
        with _patch_factory(fake):
            result = await get_user_by_id(user_id)
        assert result is user
        assert "users.id" in str(fake.executed_statements[0])


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_adds_commits_and_refreshes(self):
        fake = FakeSession()
        with _patch_factory(fake):
            result = await create_user("new@b.com", "hashedpw")
        assert result.email == "new@b.com"
        assert result.hashed_password == "hashedpw"
        assert fake.added == [result]
        assert fake.committed is True
        assert fake.refreshed == [result]


class TestGetSession:
    @pytest.mark.asyncio
    async def test_found(self):
        session_id = uuid4()
        record = SessionRecord(id=session_id, user_id=uuid4())
        fake = FakeSession(result=FakeResult(scalar=record))
        with _patch_factory(fake):
            result = await get_session(session_id)
        assert result is record


class TestGetSessionWithOwner:
    @pytest.mark.asyncio
    async def test_filters_by_both_session_id_and_user_id(self):
        session_id = uuid4()
        user_id = uuid4()
        record = SessionRecord(id=session_id, user_id=user_id)
        fake = FakeSession(result=FakeResult(scalar=record))
        with _patch_factory(fake):
            result = await get_session_with_owner(session_id, user_id)

        assert result is record
        compiled = str(fake.executed_statements[0])
        assert "sessions.id" in compiled
        assert "sessions.user_id" in compiled

    @pytest.mark.asyncio
    async def test_returns_none_for_non_owner(self):
        """Simulates a caller who isn't the session's owner -- the WHERE clause
        filters on user_id, so a mismatched owner yields no row, not the record."""
        session_id = uuid4()
        attacker_id = uuid4()
        fake = FakeSession(result=FakeResult(scalar=None))
        with _patch_factory(fake):
            result = await get_session_with_owner(session_id, attacker_id)
        assert result is None


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_adds_commits_and_refreshes(self):
        user_id = uuid4()
        fake = FakeSession()
        with _patch_factory(fake):
            result = await create_session(user_id)
        assert result.user_id == user_id
        assert fake.added == [result]
        assert fake.committed is True
        assert fake.refreshed == [result]


class TestGetSessionsForUser:
    @pytest.mark.asyncio
    async def test_returns_list_applies_limit_offset(self):
        user_id = uuid4()
        records = [SessionRecord(id=uuid4(), user_id=user_id) for _ in range(2)]
        fake = FakeSession(result=FakeResult(scalars_list=records))
        with _patch_factory(fake):
            result = await get_sessions_for_user(user_id, limit=10, offset=5)
        assert result == records
        compiled = str(fake.executed_statements[0])
        assert "sessions.user_id" in compiled
        assert "LIMIT" in compiled.upper()
        assert "OFFSET" in compiled.upper()


class TestCountSessionsForUser:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(scalar=7))
        with _patch_factory(fake):
            result = await count_sessions_for_user(user_id)
        assert result == 7

    @pytest.mark.asyncio
    async def test_none_scalar_defaults_to_zero(self):
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(scalar=None))
        with _patch_factory(fake):
            result = await count_sessions_for_user(user_id)
        assert result == 0


class TestIncrementMessageCount:
    @pytest.mark.asyncio
    async def test_increments_and_commits(self):
        session_id = uuid4()
        user_id = uuid4()
        record = SessionRecord(id=session_id, user_id=user_id, message_count=3)
        fake = FakeSession(result=FakeResult(scalar=record))
        with _patch_factory(fake):
            result = await increment_message_count(session_id, user_id)
        assert result is record
        assert fake.committed is True

    @pytest.mark.asyncio
    async def test_returns_none_when_not_owner_or_missing(self):
        session_id = uuid4()
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(scalar=None))
        with _patch_factory(fake):
            result = await increment_message_count(session_id, user_id)
        assert result is None


class TestUpdateSessionTitle:
    @pytest.mark.asyncio
    async def test_updates_title_when_owned(self):
        session_id = uuid4()
        user_id = uuid4()
        record = SessionRecord(id=session_id, user_id=user_id, title="old")
        fake = FakeSession(result=FakeResult(scalar=record))
        with _patch_factory(fake):
            result = await update_session_title(session_id, user_id, "new title")
        assert result.title == "new title"
        assert fake.committed is True
        assert fake.refreshed == [record]

    @pytest.mark.asyncio
    async def test_returns_none_and_does_not_commit_when_not_found(self):
        session_id = uuid4()
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(scalar=None))
        with _patch_factory(fake):
            result = await update_session_title(session_id, user_id, "new title")
        assert result is None
        assert fake.committed is False


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_deleted(self):
        session_id = uuid4()
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(rowcount=1))
        with _patch_factory(fake):
            result = await delete_session(session_id, user_id)
        assert result is True
        assert fake.committed is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_row_matches(self):
        """A non-owner (or nonexistent session) deletes zero rows."""
        session_id = uuid4()
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(rowcount=0))
        with _patch_factory(fake):
            result = await delete_session(session_id, user_id)
        assert result is False


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_deleted(self):
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(rowcount=1))
        with _patch_factory(fake):
            result = await delete_user(user_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_row_matches(self):
        user_id = uuid4()
        fake = FakeSession(result=FakeResult(rowcount=0))
        with _patch_factory(fake):
            result = await delete_user(user_id)
        assert result is False
