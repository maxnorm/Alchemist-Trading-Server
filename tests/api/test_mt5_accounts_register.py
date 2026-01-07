from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_register_account_with_secret_creates_token_and_returns_secret(monkeypatch):
    # Minimal payload
    payload = {
        "account_login": 12345678,
        "account_type": "live",
        "broker_name": "Test Broker",
        "broker_server": "Test-Server",
        "account_currency": "USD",
        "account_leverage": 100,
        "account_name": "Test Account",
    }

    response = client.post("/api/v1/accounts/mt5/register", json=payload)
    assert response.status_code == 201, response.text

    data = response.json()
    assert data["account_login"] == payload["account_login"]
    assert data["account_type"] == payload["account_type"]
    assert "auth_token" in data and isinstance(data["auth_token"], str)
    assert data["auth_token"]


