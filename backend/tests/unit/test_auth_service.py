from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.infrastructure.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import UserCreate
from app.services.auth_service import delete_user_account, login, refresh, signup


class TestPasswordHashing:
    def test_hash_password_creates_hash(self):
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 20
        assert hashed.startswith("$2b$")

    def test_verify_password_with_correct_password(self):
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_with_wrong_password(self):
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password("WrongPassword", hashed) is False

    def test_same_password_produces_different_hashes(self):
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    @pytest.mark.parametrize("bad_hash", ["", "not-a-real-hash", None])
    def test_verify_password_with_malformed_hash_returns_false(self, bad_hash):
        # A corrupt or empty stored hash must fail authentication cleanly
        # rather than raising and turning a login into a 500.
        assert verify_password("TestPassword123!", bad_hash) is False


class TestTokenCreation:
    def test_create_access_token_structure(self):
        user_id = uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp > now
        assert exp < now + timedelta(hours=1)

    def test_create_refresh_token_structure(self):
        user_id = uuid4()
        token = create_refresh_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp > now
        assert exp < now + timedelta(days=8)

    def test_decode_valid_token(self):
        user_id = uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_invalid_token_raises_error(self):
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token("invalid.token.here")

    def test_decode_invalid_token_preserves_cause(self):
        # The underlying jose error must be chained so the original failure
        # is preserved in tracebacks and logs.
        with pytest.raises(ValueError) as exc_info:
            decode_token("invalid.token.here")
        assert isinstance(exc_info.value.__cause__, JWTError)

    def test_decode_expired_token_raises_error(self):
        user_id = uuid4()
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)

        with patch("app.infrastructure.auth.datetime") as mock_datetime:
            mock_datetime.now.return_value = past_time
            mock_datetime.fromtimestamp = datetime.fromtimestamp
            token = create_access_token(user_id)

        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token(token)

    def test_decode_rejects_token_signed_with_wrong_key(self):
        # The whole point of a signed JWT: a token forged/re-signed under any
        # other secret must be rejected, even though it is structurally valid
        # and carries a plausible payload.
        from jose import jwt

        forged = jwt.encode(
            {
                "sub": str(uuid4()),
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            "attacker-controlled-secret",
            algorithm="HS256",
        )
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token(forged)

    def test_decode_rejects_alg_none_token(self):
        # Algorithm-confusion defence: a hand-crafted unsigned `alg=none` token
        # (the classic forgery) must be rejected. decode_token pins HS256.
        import base64
        import json

        def b64(d: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

        header = b64({"alg": "none", "typ": "JWT"})
        payload = b64({"sub": str(uuid4()), "type": "access"})
        unsigned = f"{header}.{payload}."  # empty signature
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token(unsigned)

    def test_decode_rejects_tampered_payload(self):
        # Flipping a byte in the payload segment invalidates the signature.
        token = create_access_token(uuid4())
        header, payload, sig = token.split(".")
        tampered_payload = ("A" if payload[0] != "A" else "B") + payload[1:]
        tampered = f"{header}.{tampered_payload}.{sig}"
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token(tampered)


class TestSignup:
    @pytest.mark.asyncio
    async def test_signup_creates_user(self):
        email = "test@example.com"
        password = "TestPassword123!"

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_get.return_value = None

            with patch("app.services.auth_service.create_user") as mock_create:
                mock_user = AsyncMock()
                mock_user.id = uuid4()
                mock_create.return_value = mock_user

                result = await signup(email, password)

                assert result.access_token is not None
                assert result.refresh_token is not None
                mock_get.assert_called_once_with(email)
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_signup_with_existing_email_raises_conflict(self):
        email = "existing@example.com"
        password = "TestPassword123!"

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_user = AsyncMock()
            mock_get.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await signup(email, password)

            assert exc_info.value.status_code == 409
            assert "already registered" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_signup_returns_decodable_tokens_for_new_user(self):
        # The issued tokens must carry the new user's id and the correct type so
        # downstream auth and refresh work end to end.
        user_id = uuid4()

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_get.return_value = None
            with patch("app.services.auth_service.create_user") as mock_create:
                mock_user = AsyncMock()
                mock_user.id = user_id
                mock_create.return_value = mock_user

                result = await signup("new@example.com", "TestPassword123!")

                access_payload = decode_token(result.access_token)
                refresh_payload = decode_token(result.refresh_token)
                assert access_payload["sub"] == str(user_id)
                assert access_payload["type"] == "access"
                assert refresh_payload["sub"] == str(user_id)
                assert refresh_payload["type"] == "refresh"

    @pytest.mark.asyncio
    async def test_signup_handles_concurrent_unique_violation(self):
        # A concurrent signup can insert the same email after our existence
        # check, surfacing as an IntegrityError. It must become a 409, not a 500.
        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_get.return_value = None
            with patch("app.services.auth_service.create_user") as mock_create:
                mock_create.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))

                with pytest.raises(HTTPException) as exc_info:
                    await signup("racing@example.com", "TestPassword123!")

                assert exc_info.value.status_code == 409
                assert "already registered" in exc_info.value.detail


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(self):
        email = "test@example.com"
        password = "TestPassword123!"
        hashed = hash_password(password)

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_user = AsyncMock()
            mock_user.id = uuid4()
            mock_user.hashed_password = hashed
            mock_user.is_active = True
            mock_get.return_value = mock_user

            result = await login(email, password)

            assert result.access_token is not None
            assert result.refresh_token is not None

    @pytest.mark.asyncio
    async def test_login_with_wrong_password(self):
        email = "test@example.com"
        password = "WrongPassword"
        hashed = hash_password("CorrectPassword")

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_user = AsyncMock()
            mock_user.hashed_password = hashed
            mock_get.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await login(email, password)

            assert exc_info.value.status_code == 401
            assert "Invalid email or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_with_nonexistent_email(self):
        email = "nonexistent@example.com"
        password = "TestPassword123!"

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await login(email, password)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_inactive_user(self):
        email = "test@example.com"
        password = "TestPassword123!"
        hashed = hash_password(password)

        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_user = AsyncMock()
            mock_user.hashed_password = hashed
            mock_user.is_active = False
            mock_get.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await login(email, password)

            assert exc_info.value.status_code == 403
            assert "deactivated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_verifies_password_even_when_user_missing(self):
        # Constant-time defence against email enumeration: the missing-user path
        # must still run a bcrypt verification rather than short-circuiting.
        with patch("app.services.auth_service.get_user_by_email") as mock_get:
            mock_get.return_value = None
            with patch("app.services.auth_service.verify_password") as mock_verify:
                mock_verify.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await login("ghost@example.com", "TestPassword123!")

                assert exc_info.value.status_code == 401
                mock_verify.assert_called_once()
                # Verification runs against the dummy hash, never a real one.
                from app.services.auth_service import _DUMMY_PASSWORD_HASH
                assert mock_verify.call_args.args[1] == _DUMMY_PASSWORD_HASH


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_with_valid_token(self):
        user_id = uuid4()
        refresh_token = create_refresh_token(user_id)

        with patch("app.services.auth_service.get_user_by_id") as mock_get:
            mock_user = AsyncMock()
            mock_user.id = user_id
            mock_user.is_active = True
            mock_get.return_value = mock_user

            result = await refresh(refresh_token)

            assert result.access_token is not None
            assert result.refresh_token is not None

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            await refresh("invalid.token")

        assert exc_info.value.status_code == 401
        assert "Invalid or expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_raises_error(self):
        user_id = uuid4()
        access_token = create_access_token(user_id)

        with pytest.raises(HTTPException) as exc_info:
            await refresh(access_token)

        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_with_inactive_user(self):
        user_id = uuid4()
        refresh_token = create_refresh_token(user_id)

        with patch("app.services.auth_service.get_user_by_id") as mock_get:
            mock_user = AsyncMock()
            mock_user.is_active = False
            mock_get.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await refresh(refresh_token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_nonexistent_user(self):
        user_id = uuid4()
        refresh_token = create_refresh_token(user_id)

        with patch("app.services.auth_service.get_user_by_id") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await refresh(refresh_token)

            assert exc_info.value.status_code == 401
            assert "not found or inactive" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_with_missing_subject_claim(self):
        # A validly signed refresh token with no `sub` must yield 401, not a 500
        # from the UUID parse blowing up.
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = {"type": "refresh"}

            with pytest.raises(HTTPException) as exc_info:
                await refresh("signed.but.no-sub")

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_malformed_subject_claim(self):
        # A `sub` that is not a valid UUID must also be rejected as 401.
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = {"type": "refresh", "sub": "not-a-uuid"}

            with pytest.raises(HTTPException) as exc_info:
                await refresh("signed.but.bad-sub")

            assert exc_info.value.status_code == 401


class TestDeleteUserAccount:
    @pytest.mark.asyncio
    async def test_delete_user_account(self):
        user_id = uuid4()

        with patch("app.services.auth_service.delete_user") as mock_delete:
            mock_delete.return_value = True
            result = await delete_user_account(user_id)
            assert result is True
            mock_delete.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user_account(self):
        user_id = uuid4()

        with patch("app.services.auth_service.delete_user") as mock_delete:
            mock_delete.return_value = False
            result = await delete_user_account(user_id)
            assert result is False
            mock_delete.assert_called_once_with(user_id)


class TestUserCreateModel:
    @pytest.mark.parametrize(
        "password",
        [
            "a" * 8,   # minimum length
            "a" * 72,  # 72 ASCII chars == 72 bytes, the bcrypt limit
        ],
    )
    def test_accepts_valid_password(self, password):
        user = UserCreate(email="user@example.com", password=password)
        assert user.password == password

    @pytest.mark.parametrize(
        "password",
        [
            "a" * 7,    # below min_length
            "a" * 73,   # above max_length (chars)
            "é" * 40,   # 40 chars but 80 bytes, exceeds bcrypt's 72-byte limit
        ],
    )
    def test_rejects_invalid_password(self, password):
        with pytest.raises(ValidationError):
            UserCreate(email="user@example.com", password=password)
