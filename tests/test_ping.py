import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize("method,expected_body", [("GET", b"OK"), ("HEAD", b"")])
def test_public_ping_is_tiny_and_does_not_access_user_or_provider_state(monkeypatch, method, expected_body):
    def unexpected_work(*args, **kwargs):
        raise AssertionError("Ping must not access user, database, or provider state")

    monkeypatch.setattr(main, "firebase_initialized", True)
    for name in ("load_user_keys", "get_effective_ai_clients", "get_story_path", "refresh_live_provider_models"):
        monkeypatch.setattr(main, name, unexpected_work)
    main.app.dependency_overrides[main.get_current_user_info] = unexpected_work
    main.app.dependency_overrides[main.require_authenticated_user] = unexpected_work
    try:
        with TestClient(main.app) as client:
            response = client.request(method, "/ping", follow_redirects=False)
        assert response.status_code == 200
        assert response.content == expected_body
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert response.headers["content-length"] == "2"
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers
    finally:
        main.app.dependency_overrides.clear()
