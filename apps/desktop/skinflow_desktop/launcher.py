from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import uvicorn

from skinflow_api.main import create_app
from skinflow_api.settings import Settings, get_settings

LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 58150
DEFAULT_WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1100, 720)
WINDOW_STATE_FILENAME = "desktop_window.json"
ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "skinflow.ico"
CSQAQ_TOKEN_ENV = "SKINFLOW_CSQAQ_API_TOKEN"
SINGLE_INSTANCE_MUTEX = "Local\\SkinflowDesktop"
_single_instance_handle = None


def generate_startup_token() -> str:
    """Create a fresh token for each desktop process."""
    return secrets.token_urlsafe(32)


def desktop_icon_path() -> Path:
    """Return the bundled icon when frozen and the source asset otherwise."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "apps" / "desktop" / "assets" / "skinflow.ico"
    return ICON_PATH


def window_state_path(settings: Settings) -> Path:
    return Path(settings.database_path).with_name(WINDOW_STATE_FILENAME)


def load_window_size(path: Path) -> tuple[int, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        width = int(payload["width"])
        height = int(payload["height"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return DEFAULT_WINDOW_SIZE
    return max(MIN_WINDOW_SIZE[0], width), max(MIN_WINDOW_SIZE[1], height)


def save_window_size(path: Path, width: int, height: int) -> None:
    normalized = {
        "width": max(MIN_WINDOW_SIZE[0], int(width)),
        "height": max(MIN_WINDOW_SIZE[1], int(height)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(normalized), encoding="utf-8")
    temporary.replace(path)


def read_user_environment(name: str) -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _value_type = winreg.QueryValueEx(key, name)
            return str(value).strip()
    except (ImportError, FileNotFoundError, OSError):
        return ""


def resolve_desktop_settings(settings: Settings) -> Settings:
    if settings.csqaq_api_token:
        return settings
    token = read_user_environment(CSQAQ_TOKEN_ENV)
    return settings.model_copy(update={"csqaq_api_token": token}) if token else settings


def acquire_single_instance(name: str = SINGLE_INSTANCE_MUTEX) -> bool:
    """Keep one desktop shell per user session; non-Windows callers remain testable."""
    global _single_instance_handle
    if os.name != "nt":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return False
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return False
    _single_instance_handle = handle
    return True


def release_single_instance() -> None:
    global _single_instance_handle
    if _single_instance_handle is None or os.name != "nt":
        return
    import ctypes

    ctypes.windll.kernel32.CloseHandle(_single_instance_handle)
    _single_instance_handle = None


def find_available_port(
    preferred: int = DEFAULT_PORT,
    host: str = LOCAL_HOST,
) -> int:
    """Return a free loopback port, preferring the configured desktop port."""
    candidates = [preferred] if preferred else []
    candidates.append(0)

    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return int(probe.getsockname()[1])

    raise OSError(f"No available port on {host}")


def build_server(
    settings: Settings,
    port: int,
    app_factory: Callable[[], object] | None = None,
) -> uvicorn.Server:
    """Build a single-worker server without reload or network exposure."""
    application = (app_factory or (lambda: create_app(settings)))()
    config = uvicorn.Config(
        application,
        host=LOCAL_HOST,
        port=port,
        reload=False,
        workers=1,
        access_log=False,
        log_level="warning",
    )
    return uvicorn.Server(config)


def start_desktop(settings: Settings | None = None) -> None:
    """Start FastAPI and open the local WebView2 window."""
    if not acquire_single_instance():
        return
    try:
        import webview
    except ImportError as error:  # pragma: no cover - optional desktop dependency
        release_single_instance()
        raise RuntimeError(
            "pywebview is required for the desktop shell; install the desktop extra"
        ) from error
    try:
        effective_settings = resolve_desktop_settings(settings or get_settings())
        port = find_available_port()
        token = generate_startup_token()
        desktop_settings = effective_settings.model_copy(
            update={
                "startup_token": token,
                "allowed_origin": f"http://{LOCAL_HOST}:{port}",
                "allowed_host": f"{LOCAL_HOST}:{port}",
                "serve_web": True,
            }
        )
        server = build_server(desktop_settings, port)
        thread = threading.Thread(target=server.run, name="skinflow-api", daemon=True)
        thread.start()

        state_path = window_state_path(desktop_settings)
        width, height = load_window_size(state_path)
        latest_size = [width, height]
        window = webview.create_window(
            "Skinflow · CS2 交易工作台",
            f"http://{LOCAL_HOST}:{port}/?startup_token={token}",
            width=width,
            height=height,
            min_size=MIN_WINDOW_SIZE,
        )
        if window is not None:
            window.events.resized += lambda next_width, next_height: latest_size.__setitem__(
                slice(None), [next_width, next_height]
            )
        webview.start()
        save_window_size(state_path, latest_size[0], latest_size[1])
        server.should_exit = True
        thread.join(timeout=5)
    finally:
        release_single_instance()


if __name__ == "__main__":  # pragma: no cover - process entry point
    start_desktop()
