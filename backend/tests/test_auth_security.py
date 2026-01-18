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
    ), patch("db.ConfigDoc"), patch("db.ComplianceRuleDoc"), patch("db.StoreDoc"):
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
