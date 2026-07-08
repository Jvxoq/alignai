from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.session_service import (
    check_message_threshold,
    create_user_session,
    delete_langgraph_thread,
    delete_user_session,
    get_session_messages,
    increment_session_messages,
    list_user_sessions,
    update_session_title,
    validate_session_ownership,
)


class TestValidateSessionOwnership:
    @pytest.mark.asyncio
    async def test_valid_session_and_owner(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.get_session_with_owner") as mock_get:
            mock_record = MagicMock()
            mock_record.id = session_id
            mock_record.user_id = user_id
            mock_get.return_value = mock_record

            result = await validate_session_ownership(session_id, user_id)

            assert result == mock_record
            mock_get.assert_called_once_with(session_id, user_id)

    @pytest.mark.asyncio
    async def test_nonexistent_session_raises_404(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.get_session_with_owner") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await validate_session_ownership(session_id, user_id)

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_owner_raises_404(self):
        session_id = uuid4()
        wrong_user_id = uuid4()

        with patch("app.services.session_service.get_session_with_owner") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await validate_session_ownership(session_id, wrong_user_id)

            assert exc_info.value.status_code == 404


class TestCheckMessageThreshold:
    @pytest.mark.asyncio
    async def test_under_threshold_succeeds(self):
        mock_record = MagicMock()
        mock_record.message_count = 10

        with patch("app.services.session_service.get_settings") as mock_settings:
            mock_settings.return_value.USER_MESSAGE_THRESHOLD = 50

            await check_message_threshold(mock_record)

    @pytest.mark.asyncio
    async def test_at_threshold_raises_429(self):
        mock_record = MagicMock()
        mock_record.message_count = 50

        with patch("app.services.session_service.get_settings") as mock_settings:
            mock_settings.return_value.USER_MESSAGE_THRESHOLD = 50

            with pytest.raises(HTTPException) as exc_info:
                await check_message_threshold(mock_record)

            assert exc_info.value.status_code == 429
            assert "threshold exceeded" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_over_threshold_raises_429(self):
        mock_record = MagicMock()
        mock_record.message_count = 100

        with patch("app.services.session_service.get_settings") as mock_settings:
            mock_settings.return_value.USER_MESSAGE_THRESHOLD = 50

            with pytest.raises(HTTPException) as exc_info:
                await check_message_threshold(mock_record)

            assert exc_info.value.status_code == 429


class TestIncrementSessionMessages:
    @pytest.mark.asyncio
    async def test_increment_returns_updated_record(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.increment_message_count") as mock_increment:
            mock_record = MagicMock()
            mock_record.message_count = 11
            mock_increment.return_value = mock_record

            result = await increment_session_messages(session_id, user_id)

            assert result == mock_record
            assert result.message_count == 11
            mock_increment.assert_called_once_with(session_id, user_id)

    @pytest.mark.asyncio
    async def test_increment_nonexistent_session_raises_404(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.increment_message_count") as mock_increment:
            mock_increment.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await increment_session_messages(session_id, user_id)

            assert exc_info.value.status_code == 404


class TestCreateUserSession:
    @pytest.mark.asyncio
    async def test_create_session(self):
        user_id = uuid4()

        with (
            patch("app.services.session_service.create_session") as mock_create,
            patch("app.services.session_service.count_sessions_for_user") as mock_count,
        ):
            mock_count.return_value = 0
            mock_record = MagicMock()
            mock_record.id = uuid4()
            mock_record.user_id = user_id
            mock_create.return_value = mock_record

            result = await create_user_session(user_id)

            assert result == mock_record
            mock_create.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_create_session_at_limit_raises_409(self):
        user_id = uuid4()

        with (
            patch("app.services.session_service.create_session") as mock_create,
            patch("app.services.session_service.count_sessions_for_user") as mock_count,
        ):
            mock_count.return_value = 3

            with pytest.raises(HTTPException) as exc_info:
                await create_user_session(user_id)

            assert exc_info.value.status_code == 409
            mock_create.assert_not_called()


class TestListUserSessions:
    @pytest.mark.asyncio
    async def test_list_sessions(self):
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_sessions_for_user") as mock_get,
            patch("app.infrastructure.database.count_sessions_for_user") as mock_count,
        ):
            mock_sessions = [MagicMock(), MagicMock(), MagicMock()]
            mock_get.return_value = mock_sessions
            mock_count.return_value = 3

            sessions, total = await list_user_sessions(user_id)

            assert sessions == mock_sessions
            assert total == 3
            mock_get.assert_called_once_with(user_id, 50, 0)
            mock_count.assert_called_once_with(user_id)


class TestDeleteUserSession:
    @pytest.mark.asyncio
    async def test_delete_existing_session(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.delete_session") as mock_delete:
            mock_delete.return_value = True

            with patch("app.services.session_service.delete_langgraph_thread") as mock_delete_thread:
                result = await delete_user_session(session_id, user_id)

                assert result is True
                mock_delete.assert_called_once_with(session_id, user_id)
                mock_delete_thread.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.delete_session") as mock_delete:
            mock_delete.return_value = False

            with patch("app.services.session_service.delete_langgraph_thread") as mock_delete_thread:
                result = await delete_user_session(session_id, user_id)

                assert result is False
                mock_delete_thread.assert_not_called()


class TestUpdateSessionTitle:
    @pytest.mark.asyncio
    async def test_update_title_success(self):
        session_id = uuid4()
        user_id = uuid4()
        new_title = "Updated Title"

        with patch("app.services.session_service.update_session_title_db") as mock_update:
            mock_record = MagicMock()
            mock_record.title = new_title
            mock_update.return_value = mock_record

            result = await update_session_title(session_id, user_id, new_title)

            assert result.title == new_title
            mock_update.assert_called_once_with(session_id, user_id, new_title)

    @pytest.mark.asyncio
    async def test_update_title_nonexistent_session(self):
        session_id = uuid4()
        user_id = uuid4()

        with patch("app.services.session_service.update_session_title_db") as mock_update:
            mock_update.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await update_session_title(session_id, user_id, "New Title")

            assert exc_info.value.status_code == 404


class TestGetSessionMessages:
    def _own_session(self, mock_get_owner, session_id, user_id):
        mock_record = MagicMock()
        mock_record.id = session_id
        mock_record.user_id = user_id
        mock_get_owner.return_value = mock_record

    @pytest.mark.asyncio
    async def test_rejects_non_owner_before_hitting_langgraph(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            mock_get_owner.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_session_messages(session_id, user_id)

            assert exc_info.value.status_code == 404
            mock_client_getter.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_shaped_thread_values_dict_messages(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(return_value={
                "values": [
                    {"type": "human", "content": "What is Article 5?"},
                    {"type": "ai", "content": "Article 5 prohibits..."},
                ]
            })
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert len(result) == 2
            assert result[0].role == "user"
            assert result[0].content == "What is Article 5?"
            assert result[1].role == "assistant"
            assert result[1].content == "Article 5 prohibits..."

    @pytest.mark.asyncio
    async def test_dict_shaped_thread_values_dict_messages(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(return_value={
                "values": {
                    "messages": [
                        {"type": "human", "content": "Hello"},
                        {"role": "system", "content": "System note"},
                    ]
                }
            })
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert len(result) == 2
            assert result[0].role == "user"
            assert result[0].content == "Hello"
            assert result[1].role == "system"
            assert result[1].content == "System note"

    @pytest.mark.asyncio
    async def test_object_shaped_messages_use_attributes(self):
        session_id = uuid4()
        user_id = uuid4()

        class FakeMsg:
            def __init__(self, type_, content):
                self.type = type_
                self.content = content

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(return_value={
                "values": [FakeMsg("ai", "An object-based message")]
            })
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert len(result) == 1
            assert result[0].role == "assistant"
            assert result[0].content == "An object-based message"

    @pytest.mark.asyncio
    async def test_messages_missing_role_or_content_are_dropped(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(return_value={
                "values": [
                    {"type": "", "content": "no type"},
                    {"type": "human", "content": ""},
                    {"type": "human", "content": "kept"},
                ]
            })
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert len(result) == 1
            assert result[0].content == "kept"

    @pytest.mark.asyncio
    async def test_unrecognized_thread_values_shape_returns_empty(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(return_value={"values": "unexpected string"})
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert result == []

    @pytest.mark.asyncio
    async def test_langgraph_get_state_failure_returns_empty_list(self):
        session_id = uuid4()
        user_id = uuid4()

        with (
            patch("app.services.session_service.get_session_with_owner") as mock_get_owner,
            patch("app.services.session_service.get_langgraph_client") as mock_client_getter,
        ):
            self._own_session(mock_get_owner, session_id, user_id)
            mock_client = MagicMock()
            mock_client.threads.get_state = AsyncMock(side_effect=RuntimeError("langgraph unreachable"))
            mock_client_getter.return_value = mock_client

            result = await get_session_messages(session_id, user_id)

            assert result == []


class TestDeleteLanggraphThread:
    @pytest.mark.asyncio
    async def test_deletes_thread(self):
        session_id = uuid4()

        with patch("app.services.session_service.get_langgraph_client") as mock_client_getter:
            mock_client = MagicMock()
            mock_client.threads.delete = AsyncMock(return_value=None)
            mock_client_getter.return_value = mock_client

            await delete_langgraph_thread(session_id)

            mock_client.threads.delete.assert_called_once_with(str(session_id))

    @pytest.mark.asyncio
    async def test_swallows_delete_failure(self):
        session_id = uuid4()

        with patch("app.services.session_service.get_langgraph_client") as mock_client_getter:
            mock_client = MagicMock()
            mock_client.threads.delete = AsyncMock(side_effect=RuntimeError("thread gone"))
            mock_client_getter.return_value = mock_client

            await delete_langgraph_thread(session_id)  # should not raise
