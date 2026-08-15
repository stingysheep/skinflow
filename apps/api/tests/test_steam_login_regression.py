from http.cookies import SimpleCookie
from types import SimpleNamespace

import pytest

from skinflow_api.application.inventory.errors import LoginUnavailable
from skinflow_api.infrastructure.platforms.steam.login import SteamLoginCoordinator
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    PersistentSteamSession,
    SteamCredentials,
)


def test_browser_runtime_gets_actionable_desktop_login_error(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "webview", SimpleNamespace(windows=[]))
    coordinator = SteamLoginCoordinator(InMemorySteamSession())

    with pytest.raises(LoginUnavailable, match="Skinflow 桌面版"):
        coordinator.start()


def test_login_coordinator_activates_session_and_closes_window(monkeypatch) -> None:
    login = SimpleCookie()
    login.load("steamLoginSecure=76561198000000000%7C%7Ctoken")
    session_cookie = SimpleCookie()
    session_cookie.load("sessionid=csrf")

    class Window:
        events = SimpleNamespace(closed=SimpleNamespace(is_set=lambda: False))
        destroyed = False

        def get_cookies(self):
            return [login, session_cookie]

        def destroy(self):
            self.destroyed = True

    window = Window()
    monkeypatch.setitem(
        __import__("sys").modules,
        "webview",
        SimpleNamespace(create_window=lambda *_args, **_kwargs: window),
    )
    steam_session = InMemorySteamSession()
    coordinator = SteamLoginCoordinator(steam_session)

    coordinator._run()

    assert coordinator.status()["status"] == "active"
    assert window.destroyed is True


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows DPAPI only")
def test_persistent_session_survives_process_reconstruction(tmp_path) -> None:
    path = tmp_path / "steam_session.bin"
    credentials = SteamCredentials("76561198000000000", "76561198000000000%7C%7Ctoken", "csrf")

    first = PersistentSteamSession(path)
    first.set_credentials(credentials)
    second = PersistentSteamSession(path)

    assert second.status().status.value == "active"
    assert second.credentials() == credentials
    second.clear()
    assert not path.exists()
