from __future__ import annotations

import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import unquote

from skinflow_api.application.inventory.errors import LoginUnavailable

from .session import InMemorySteamSession, SteamCredentials

LOGIN_URL = "https://steamcommunity.com/login/home/?goto=market"
LOGIN_TIMEOUT_SECONDS = 600


def extract_credentials(cookies: object) -> SteamCredentials | None:
    login_secure: str | None = None
    sessionid: str | None = None
    for cookie in cookies or []:
        if isinstance(cookie, SimpleCookie):
            if "steamLoginSecure" in cookie:
                login_secure = cookie["steamLoginSecure"].value
            if "sessionid" in cookie:
                sessionid = cookie["sessionid"].value
        elif isinstance(cookie, dict):
            name = str(cookie.get("name") or "")
            if name == "steamLoginSecure":
                login_secure = str(cookie.get("value") or "")
            elif name == "sessionid":
                sessionid = str(cookie.get("value") or "")
    if not login_secure or not sessionid:
        return None
    decoded = unquote(login_secure)
    steamid64, separator, token = decoded.partition("||")
    if separator != "||" or not token or len(steamid64) != 17 or not steamid64.isdigit():
        return None
    return SteamCredentials(steamid64, login_secure, sessionid)


class SteamLoginCoordinator:
    def __init__(self, session: InMemorySteamSession) -> None:
        self._session = session
        self._lock = threading.RLock()
        self._running = False
        self._error: str | None = None

    def status(self) -> dict:
        session = self._session.status()
        with self._lock:
            return {
                "status": session.status,
                "steamid64": session.steamid64,
                "login_running": self._running,
                "error": self._error,
            }

    def start(self) -> dict:
        with self._lock:
            if self._running:
                return self.status()
            self._validate_desktop()
            self._running = True
            self._error = None
        threading.Thread(target=self._run, name="steam-login", daemon=True).start()
        return self.status()

    def clear(self) -> dict:
        self._session.clear()
        return self.status()

    @staticmethod
    def _validate_desktop() -> None:
        try:
            import webview
        except ImportError as error:
            raise LoginUnavailable("当前未安装桌面运行组件，请使用 Skinflow 桌面版") from error
        if not getattr(webview, "windows", None):
            raise LoginUnavailable("Steam 登录只能在 Skinflow 桌面版中使用")

    def _run(self) -> None:
        try:
            import webview

            window = webview.create_window("登录 Steam", LOGIN_URL, width=1080, height=800)
            deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if window.events.closed.is_set():
                    raise RuntimeError("Steam 登录窗口已关闭，未检测到有效会话")
                try:
                    credentials = extract_credentials(window.get_cookies())
                except Exception:
                    credentials = None
                if credentials is not None:
                    self._session.set_credentials(credentials)
                    window.destroy()
                    return
                time.sleep(1)
            raise TimeoutError("Steam 登录超时，未检测到有效会话，请关闭窗口后重试")
        except Exception as error:
            with self._lock:
                self._error = str(error) or type(error).__name__
        finally:
            with self._lock:
                self._running = False
