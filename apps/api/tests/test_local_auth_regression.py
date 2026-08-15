from pathlib import Path

from fastapi.testclient import TestClient

from skinflow_api.main import create_app
from skinflow_api.routes.local_auth import session_cookie_name
from skinflow_api.settings import Settings


def desktop_settings(path: Path, token: str, port: int) -> Settings:
    origin = f"http://127.0.0.1:{port}"
    return Settings(
        environment="test",
        database_path=str(path),
        startup_token=token,
        allowed_origin=origin,
        allowed_host=f"127.0.0.1:{port}",
    )


def test_desktop_instances_use_independent_session_cookies(tmp_path: Path) -> None:
    first = desktop_settings(tmp_path / "first.db", "a" * 32, 58150)
    second = desktop_settings(tmp_path / "second.db", "b" * 32, 57243)
    first_cookie = session_cookie_name(first)
    second_cookie = session_cookie_name(second)

    assert first_cookie != second_cookie

    shared_browser_cookies = {
        first_cookie: first.startup_token,
        second_cookie: second.startup_token,
    }
    with TestClient(
        create_app(first),
        base_url=first.allowed_origin,
        cookies=shared_browser_cookies,
    ) as first_client:
        first_response = first_client.post(
            "/api/purchases", json={}, headers={"Origin": first.allowed_origin}
        )
    with TestClient(
        create_app(second),
        base_url=second.allowed_origin,
        cookies=shared_browser_cookies,
    ) as second_client:
        second_response = second_client.post(
            "/api/purchases", json={}, headers={"Origin": second.allowed_origin}
        )

    assert first_response.status_code == 422
    assert second_response.status_code == 422
