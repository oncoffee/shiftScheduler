import hashlib
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


_mock_gspread = MagicMock()
_mock_gc = MagicMock()
_mock_book = MagicMock()
_mock_book.worksheet.return_value.get_all_records.return_value = []
_mock_gc.open_by_key.return_value = _mock_book
_mock_gspread.service_account.return_value = _mock_gc

_mock_motor = MagicMock()


@pytest.fixture(scope="module", autouse=True)
def mock_dependencies():
    with patch.dict(
        sys.modules,
        {
            "gspread": _mock_gspread,
            "motor": _mock_motor,
            "motor.motor_asyncio": _mock_motor,
        },
    ):
        yield


class TestTokenHashing:
    def test_hash_token_uses_bcrypt_context(self):
        from auth.token_hash import pwd_context

        assert "bcrypt" in pwd_context.schemes()

    def test_hash_token_returns_hash(self):
        with patch("auth.token_hash.pwd_context") as mock_ctx:
            mock_ctx.hash.return_value = "$2b$12$mockedhashvalue"
            from auth.token_hash import hash_token

            from importlib import reload
            import auth.token_hash
            reload(auth.token_hash)

            with patch.object(auth.token_hash.pwd_context, "hash", return_value="$2b$12$mockedhash"):
                result = auth.token_hash.hash_token("test_token")
                assert result == "$2b$12$mockedhash"

    def test_verify_token_returns_true_on_match(self):
        import auth.token_hash
        with patch.object(auth.token_hash.pwd_context, "verify", return_value=True):
            result = auth.token_hash.verify_token("token", "hashed")
            assert result is True

    def test_verify_token_returns_false_on_mismatch(self):
        import auth.token_hash
        with patch.object(auth.token_hash.pwd_context, "verify", return_value=False):
            result = auth.token_hash.verify_token("wrong_token", "hashed")
            assert result is False

    def test_hash_and_verify_integration(self):
        import auth.token_hash

        mock_hash = "$2b$12$abcdefghijklmnopqrstuv"

        with patch.object(auth.token_hash.pwd_context, "hash", return_value=mock_hash):
            hashed = auth.token_hash.hash_token("my_token")

        with patch.object(auth.token_hash.pwd_context, "verify", return_value=True):
            assert auth.token_hash.verify_token("my_token", hashed) is True

        with patch.object(auth.token_hash.pwd_context, "verify", return_value=False):
            assert auth.token_hash.verify_token("wrong_token", hashed) is False


class TestOAuthStateDoc:
    def test_oauth_state_model_has_required_fields(self, mock_dependencies):
        from db.models import OAuthStateDoc

        model_fields = OAuthStateDoc.model_fields
        assert "state" in model_fields
        assert "created_at" in model_fields

    def test_oauth_state_collection_name(self, mock_dependencies):
        from db.models import OAuthStateDoc

        assert OAuthStateDoc.Settings.name == "oauth_states"

    def test_oauth_state_has_ttl_index(self, mock_dependencies):
        from db.models import OAuthStateDoc

        indexes = OAuthStateDoc.Settings.indexes
        ttl_found = False
        for idx in indexes:
            idx_str = str(idx)
            if "expireAfterSeconds" in idx_str:
                ttl_found = True
                break

        assert ttl_found, "OAuthStateDoc should have a TTL index"


class _QueryFieldMock:
    def __ge__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __lt__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()


def _create_document_mock_with_fields():
    mock_doc = MagicMock()
    mock_doc.state = _QueryFieldMock()
    mock_doc.email = _QueryFieldMock()
    mock_doc.google_id = _QueryFieldMock()
    return mock_doc


@pytest.fixture
def mock_db(mock_dependencies):
    mock_user = _create_document_mock_with_fields()
    mock_oauth_state = _create_document_mock_with_fields()
    mock_whitelist = _create_document_mock_with_fields()

    mock_state_instance = MagicMock()
    mock_state_instance.insert = AsyncMock()
    mock_state_instance.delete = AsyncMock()
    mock_oauth_state.return_value = mock_state_instance

    with patch("app.init_db", new_callable=AsyncMock), patch(
        "app.close_db", new_callable=AsyncMock
    ), patch("app.EmployeeDoc"), patch("app.StoreDoc"), patch(
        "app.ConfigDoc"
    ), patch("app.ScheduleRunDoc"), patch("app.ComplianceRuleDoc"), patch(
        "app.AssignmentDoc"
    ), patch("app.DailySummaryDoc"), patch("app.AssignmentEditDoc"), patch(
        "app.UserDoc", mock_user
    ), patch("app.EmailWhitelistDoc", mock_whitelist), patch(
        "app.OAuthStateDoc", mock_oauth_state
    ), patch("db.ConfigDoc"), patch("db.ComplianceRuleDoc"), patch("db.StoreDoc"), patch(
        "auth.dependencies.UserDoc", mock_user
    ):
        mock_user.find_one = AsyncMock(return_value=None)
        mock_whitelist.find_one = AsyncMock(return_value=None)
        mock_oauth_state.find_one = AsyncMock(return_value=None)

        yield {
            "UserDoc": mock_user,
            "EmailWhitelistDoc": mock_whitelist,
            "OAuthStateDoc": mock_oauth_state,
        }


@pytest.fixture
def client(mock_dependencies, mock_db):
    from fastapi.testclient import TestClient
    from app import app

    return TestClient(app)


class TestAuthLoginRateLimiting:
    def test_login_returns_auth_url(self, client, mock_db):
        response = client.get("/auth/login")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]

    def test_login_creates_oauth_state_in_db(self, client, mock_db):
        response = client.get("/auth/login")

        assert response.status_code == 200
        mock_db["OAuthStateDoc"].assert_called_once()


class TestAuthCallbackSecurity:
    def test_callback_rejects_invalid_state(self, client, mock_db):
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=None)

        response = client.get("/auth/callback?code=test_code&state=invalid_state")

        assert response.status_code == 400
        assert "Invalid or expired state" in response.json()["detail"]

    def test_callback_deletes_state_after_use(self, client, mock_db):
        mock_state = MagicMock()
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"error": "invalid_grant", "error_description": "test"}
            response = client.get("/auth/callback?code=test_code&state=valid_state")

        mock_state.delete.assert_called_once()


class TestRefreshTokenSecurity:
    def test_refresh_uses_bcrypt_verification(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        refresh_token, _ = create_refresh_token("test@example.com")
        stored_hash = "bcrypt_hashed_value"

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = stored_hash
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        with patch("app.verify_token", return_value=True) as mock_verify:
            response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

            mock_verify.assert_called_once_with(refresh_token, stored_hash)

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_refresh_rejects_wrong_token(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        wrong_token, _ = create_refresh_token("test@example.com")
        stored_hash = "bcrypt_hashed_value"

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = stored_hash
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        with patch("app.verify_token", return_value=False):
            response = client.post("/auth/refresh", json={"refresh_token": wrong_token})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_rejects_invalid_jwt(self, client, mock_db):
        response = client.post("/auth/refresh", json={"refresh_token": "not.a.valid.jwt"})

        assert response.status_code == 401

    def test_refresh_rejects_access_token_type(self, client, mock_db):
        from auth.jwt_handler import create_access_token

        access_token = create_access_token("test@example.com", "user123", "viewer")

        response = client.post("/auth/refresh", json={"refresh_token": access_token})

        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]


class TestRateLimitingConfiguration:
    def test_app_has_rate_limiter_configured(self, mock_dependencies):
        from app import app

        assert hasattr(app.state, "limiter")

    def test_rate_limit_exceeded_handler_registered(self, mock_dependencies):
        from app import app
        from slowapi.errors import RateLimitExceeded

        assert RateLimitExceeded in app.exception_handlers


class TestStateTokenExpiration:

    def test_expired_state_token_rejected(self, client, mock_db):
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=None)

        response = client.get("/auth/callback?code=valid_code&state=expired_state")

        assert response.status_code == 400
        assert "Invalid or expired state" in response.json()["detail"]

    def test_state_token_deleted_after_callback_even_on_error(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "valid_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"error": "invalid_grant", "error_description": "Code expired"}
            response = client.get("/auth/callback?code=old_code&state=valid_state")

        mock_state.delete.assert_called_once()
        assert response.status_code == 400


class TestStateTokenReplayAttacks:

    def test_state_token_replay_attack_prevented(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "unique_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()

        mock_db["OAuthStateDoc"].find_one = AsyncMock(side_effect=[mock_state, None])

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {"error": "invalid_grant"}

            response1 = client.get("/auth/callback?code=code1&state=unique_state")

            response2 = client.get("/auth/callback?code=code2&state=unique_state")

        assert response1.status_code == 400

        assert response2.status_code == 400
        assert "Invalid or expired state" in response2.json()["detail"]

    def test_state_token_deleted_immediately_on_valid_callback(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "valid_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        delete_called_before_exchange = False

        async def mock_exchange(code):
            nonlocal delete_called_before_exchange
            delete_called_before_exchange = mock_state.delete.called
            return {"error": "invalid_grant"}

        with patch("app.exchange_code_for_tokens", side_effect=mock_exchange):
            client.get("/auth/callback?code=test_code&state=valid_state")

        assert delete_called_before_exchange


class TestCSRFProtection:

    def test_callback_without_state_parameter_fails(self, client, mock_db):
        response = client.get("/auth/callback?code=test_code")

        assert response.status_code == 422

    def test_callback_with_empty_state_fails(self, client, mock_db):
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=None)

        response = client.get("/auth/callback?code=test_code&state=")

        assert response.status_code in [400, 422]

    def test_callback_with_tampered_state_fails(self, client, mock_db):
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=None)

        response = client.get("/auth/callback?code=valid_code&state=attacker_state")

        assert response.status_code == 400
        assert "Invalid or expired state" in response.json()["detail"]

    def test_state_is_cryptographically_random(self, client, mock_db):
        states = []

        def capture_state(*args, **kwargs):
            mock_instance = MagicMock()
            mock_instance.insert = AsyncMock()
            if args:
                states.append(kwargs.get('state', getattr(args[0], 'state', None)))
            return mock_instance

        mock_db["OAuthStateDoc"].side_effect = capture_state

        for _ in range(5):
            response = client.get("/auth/login")
            assert response.status_code == 200
            data = response.json()
            assert "state" in data
            states.append(data["state"])

        assert len(states) == len(set(states)), "State tokens must be unique"

        for state in states:
            assert len(state) >= 32, "State token should be at least 32 characters"


class TestInvalidAuthorizationCodes:

    @pytest.fixture(autouse=True)
    def disable_rate_limit(self, client):
        from app import app
        limiter = app.state.limiter
        limiter.enabled = False
        yield
        limiter.enabled = True

    def test_invalid_authorization_code_rejected(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "valid_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {
                "error": "invalid_grant",
                "error_description": "Bad Request"
            }

            response = client.get("/auth/callback?code=invalid_code&state=valid_state")

        assert response.status_code == 400
        assert "Bad Request" in response.json()["detail"]

    def test_expired_authorization_code_rejected(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "expired_code_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {
                "error": "invalid_grant",
                "error_description": "Code was already redeemed."
            }

            response = client.get("/auth/callback?code=already_used_code&state=expired_code_state")

        assert response.status_code == 400
        assert "already redeemed" in response.json()["detail"]

    def test_malformed_authorization_code_handled(self, client, mock_db):
        from datetime import datetime, timezone
        import urllib.parse

        mock_state = MagicMock()
        mock_state.state = "malformed_test_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = {
                "error": "invalid_request",
                "error_description": "Malformed auth code."
            }

            malformed_code = urllib.parse.quote("' OR 1=1 --")
            response = client.get(f"/auth/callback?code={malformed_code}&state=malformed_test_state")
            assert response.status_code == 400

    def test_invalid_id_token_rejected(self, client, mock_db):
        from datetime import datetime, timezone

        mock_state = MagicMock()
        mock_state.state = "id_token_test_state"
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.delete = AsyncMock()
        mock_db["OAuthStateDoc"].find_one = AsyncMock(return_value=mock_state)

        with patch("app.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange, \
             patch("app.verify_google_id_token") as mock_verify:
            mock_exchange.return_value = {
                "access_token": "fake_access",
                "id_token": "invalid_id_token",
                "token_type": "Bearer"
            }
            mock_verify.side_effect = ValueError("Invalid token signature")

            response = client.get("/auth/callback?code=valid_code&state=id_token_test_state")

        assert response.status_code == 400
        assert "Invalid ID token" in response.json()["detail"]


class TestTokenExpirationHandling:

    def test_expired_access_token_rejected(self, mock_dependencies, mock_db):
        from datetime import datetime, timedelta, timezone
        import jwt
        from fastapi.testclient import TestClient
        from auth.config import JWT_SECRET_KEY
        from app import app

        app.dependency_overrides.clear()

        expired_payload = {
            "sub": "expired_test@example.com",
            "user_id": "user123",
            "role": "viewer",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=35),
            "type": "access",
        }

        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm="HS256")

        test_client = TestClient(app)
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_expired_refresh_token_rejected(self, client, mock_db):
        from datetime import datetime, timedelta, timezone
        import jwt
        from auth.config import JWT_SECRET_KEY

        expired_payload = {
            "sub": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
            "iat": datetime.now(timezone.utc) - timedelta(days=8),
            "type": "refresh",
        }

        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm="HS256")

        response = client.post(
            "/auth/refresh",
            json={"refresh_token": expired_token}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_refresh_token_near_expiration_still_works(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        refresh_token, _ = create_refresh_token("test@example.com")

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = "stored_hash"
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        with patch("app.verify_token", return_value=True):
            response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert "access_token" in response.json()


class TestRefreshTokenRotationSecurity:

    def test_refresh_token_hash_verified_not_plain_text(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        refresh_token, _ = create_refresh_token("test@example.com")

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = refresh_token
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        with patch("app.verify_token", return_value=False) as mock_verify:
            response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
            mock_verify.assert_called_once_with(refresh_token, refresh_token)

        assert response.status_code == 401

    def test_refresh_rejects_token_for_different_user(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        user_a_token, _ = create_refresh_token("userA@example.com")

        mock_user_b = MagicMock()
        mock_user_b.id = "userB123"
        mock_user_b.email = "userB@example.com"
        mock_user_b.role = "viewer"
        mock_user_b.refresh_token_hash = "userB_hash"

        mock_db["UserDoc"].find_one = AsyncMock(return_value=None)

        response = client.post("/auth/refresh", json={"refresh_token": user_a_token})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_fails_when_user_has_no_stored_hash(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        refresh_token, _ = create_refresh_token("test@example.com")

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = None
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_old_refresh_token_invalid_after_new_login(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        old_token, _ = create_refresh_token("test@example.com")

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = "new_hash_from_new_login"
        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        with patch("app.verify_token", return_value=False):
            response = client.post("/auth/refresh", json={"refresh_token": old_token})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]


class TestLogoutInvalidatesRefreshToken:

    def test_logout_clears_refresh_token_hash(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from auth.jwt_handler import create_access_token
        from auth.dependencies import get_current_user
        from app import app

        access_token = create_access_token("logout_test@example.com", "user123", "viewer")

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "logout_test@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = "existing_hash"
        mock_user.refresh_token_expires_at = MagicMock()
        mock_user.save = AsyncMock()

        async def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user
        try:
            test_client = TestClient(app)
            response = test_client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            assert response.status_code == 200
            assert mock_user.refresh_token_hash is None
            assert mock_user.refresh_token_expires_at is None
            mock_user.save.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_refresh_fails_after_logout(self, client, mock_db):
        from auth.jwt_handler import create_refresh_token

        refresh_token, _ = create_refresh_token("logout_refresh@example.com")

        mock_user = MagicMock()
        mock_user.id = "user456"
        mock_user.email = "logout_refresh@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = None
        mock_user.refresh_token_expires_at = None
        mock_user.save = AsyncMock()

        mock_db["UserDoc"].find_one = AsyncMock(return_value=mock_user)

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_logout_requires_authentication_no_header(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from app import app

        app.dependency_overrides.clear()

        test_client = TestClient(app)
        response = test_client.post("/auth/logout")
        assert response.status_code == 401

    def test_logout_requires_authentication_invalid_token(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from app import app

        app.dependency_overrides.clear()

        test_client = TestClient(app)
        response = test_client.post(
            "/auth/logout",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_logout_with_refresh_token_fails(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from auth.jwt_handler import create_refresh_token
        from app import app

        app.dependency_overrides.clear()

        refresh_token, _ = create_refresh_token("logout_reject@example.com")

        test_client = TestClient(app)
        response = test_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]

    def test_multiple_logouts_are_idempotent(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from auth.jwt_handler import create_access_token
        from auth.dependencies import get_current_user
        from app import app

        access_token = create_access_token("multiple_logout@example.com", "user789", "viewer")

        mock_user = MagicMock()
        mock_user.id = "user789"
        mock_user.email = "multiple_logout@example.com"
        mock_user.role = "viewer"
        mock_user.refresh_token_hash = None
        mock_user.refresh_token_expires_at = None
        mock_user.save = AsyncMock()

        async def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user
        try:
            test_client = TestClient(app)

            response1 = test_client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response1.status_code == 200

            response2 = test_client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response2.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestTokenTypeValidation:

    def test_access_token_rejected_for_refresh(self, client, mock_db):
        from auth.jwt_handler import create_access_token

        access_token = create_access_token("test@example.com", "user123", "viewer")

        response = client.post("/auth/refresh", json={"refresh_token": access_token})

        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]

    def test_refresh_token_rejected_for_protected_endpoints(self, mock_dependencies, mock_db):
        from fastapi.testclient import TestClient
        from auth.jwt_handler import create_refresh_token
        from app import app

        app.dependency_overrides.clear()

        refresh_token, _ = create_refresh_token("type_test@example.com")

        test_client = TestClient(app)
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]

    def test_token_without_type_claim_rejected(self, mock_dependencies, mock_db):
        import jwt
        from datetime import datetime, timedelta, timezone
        from fastapi.testclient import TestClient
        from auth.config import JWT_SECRET_KEY
        from app import app

        app.dependency_overrides.clear()

        payload = {
            "sub": "no_type@example.com",
            "user_id": "user123",
            "role": "viewer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

        test_client = TestClient(app)
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

    def test_token_with_wrong_algorithm_rejected(self, mock_dependencies, mock_db):
        import jwt
        from datetime import datetime, timedelta, timezone
        from fastapi.testclient import TestClient
        from auth.config import JWT_SECRET_KEY
        from app import app

        app.dependency_overrides.clear()

        payload = {
            "sub": "wrong_algo@example.com",
            "user_id": "user123",
            "role": "viewer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS384")

        test_client = TestClient(app)
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
