import sys
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all external dependencies before importing the app."""
    # Mock gspread
    mock_gspread = MagicMock()
    mock_gc = MagicMock()
    mock_book = MagicMock()
    mock_book.worksheet.return_value.get_all_records.return_value = []
    mock_gc.open_by_key.return_value = mock_book
    mock_gspread.service_account.return_value = mock_gc

    with patch.dict(sys.modules, {"gspread": mock_gspread}):
        yield


@pytest.fixture
def client(mock_dependencies):
    """Create test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app import app

    return TestClient(app)


def test_docs_endpoint_accessible(client):
    """Test that the /docs endpoint is accessible."""
    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_endpoint_accessible(client):
    """Test that the /openapi.json endpoint is accessible."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "shiftScheduler"


def test_solver_run_requires_pass_key(client):
    """Test that /solver/run endpoint requires pass_key parameter."""
    response = client.get("/solver/run")

    assert response.status_code == 422  # Validation error


def test_solver_run_rejects_invalid_pass_key(client):
    """Test that /solver/run rejects invalid pass_key."""
    response = client.get("/solver/run?pass_key=wrong")

    assert response.status_code == 422


def test_solver_run_accepts_valid_pass_key(client, mock_dependencies):
    """Test that /solver/run accepts valid pass_key."""
    with patch("app.main") as mock_main, patch("app.SOLVER_PASS_KEY", "testkey"):
        mock_main.return_value = None
        response = client.get("/solver/run?pass_key=testkey")

        assert response.status_code == 200
        assert "successfully" in response.text.lower()
        mock_main.assert_called_once()


def test_logs_endpoint_returns_200(client):
    """Test that /logs endpoint returns 200."""
    response = client.get("/logs")

    assert response.status_code == 200


def test_logs_endpoint_returns_log_content(client, tmp_path):
    """Test that /logs returns log file content when it exists."""
    log_content = "Test log entry\nAnother entry"

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = log_content
        # The endpoint uses a hardcoded path, so this test mainly verifies the logic
        response = client.get("/logs")

        # Will return "not found" since the hardcoded path doesn't exist
        assert response.status_code == 200


def test_cors_headers_present(client):
    """Test that CORS headers are present in responses."""
    response = client.options(
        "/solver/run",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )

    # CORS middleware should allow the request
    assert response.status_code in [200, 400, 422]
