from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import aiohttp

from skinflow_api.application.scan.upstream_errors import UpstreamUnavailable

PAGE_URL = "https://www.youpin898.com/market/goods-list?templateId={template_id}"


class EdgeYoupinBrowser:
    """Lazily capture the public page's normal listing response through Edge CDP."""

    def __init__(self, *, timeout_seconds: float = 25.0, idle_seconds: float = 60.0) -> None:
        self._timeout = timeout_seconds
        self._idle_seconds = idle_seconds
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._start_lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._profile: Path | None = None
        self._port: int | None = None
        self._browser_lock: asyncio.Lock | None = None
        self._active = 0
        self._idle_task: asyncio.Task[None] | None = None

    def fetch_listing_payload(self, template_id: int) -> dict:
        if template_id < 1:
            raise UpstreamUnavailable("missing youpin template id")
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(self._fetch(template_id), loop)
        try:
            return future.result(timeout=self._timeout + 8)
        except TimeoutError as error:
            future.cancel()
            raise UpstreamUnavailable("youpin page timed out") from error

    def close(self) -> None:
        with self._start_lock:
            loop = self._loop
            thread = self._thread
        if loop is None or thread is None:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._stop_browser(), loop)
            future.result(timeout=5)
        except (RuntimeError, TimeoutError):
            with self._start_lock:
                process = self._process
            if process is not None and process.poll() is None:
                _kill_windows_process_tree(process.pid)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        with self._start_lock:
            self._loop = None
            self._thread = None
            self._ready.clear()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._ready.clear()
                self._thread = threading.Thread(
                    target=self._run_loop,
                    name="skinflow-youpin-edge",
                    daemon=True,
                )
                self._thread.start()
        if not self._ready.wait(timeout=5) or self._loop is None:
            raise UpstreamUnavailable("unable to start youpin browser worker")
        return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._browser_lock = asyncio.Lock()
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    async def _fetch(self, template_id: int) -> dict:
        self._active += 1
        if self._idle_task is not None:
            self._idle_task.cancel()
            self._idle_task = None
        try:
            await self._ensure_browser()
            return await asyncio.wait_for(
                self._capture_response(template_id), timeout=self._timeout
            )
        except (TimeoutError, aiohttp.ClientError, OSError, ValueError) as error:
            raise UpstreamUnavailable(f"youpin browser: {type(error).__name__}") from error
        finally:
            self._active -= 1
            if self._active == 0:
                self._idle_task = asyncio.create_task(self._idle_shutdown())

    async def _ensure_browser(self) -> None:
        if self._process is not None and self._process.poll() is None and self._port:
            return
        assert self._browser_lock is not None
        async with self._browser_lock:
            if self._process is not None and self._process.poll() is None and self._port:
                return
            edge = _find_edge()
            _cleanup_stale_profiles()
            self._profile = Path(tempfile.mkdtemp(prefix="skinflow-youpin-"))
            flags = 0x08000000 if os.name == "nt" else 0
            self._process = subprocess.Popen(
                [
                    str(edge),
                    "--headless=new",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-extensions",
                    "--disable-sync",
                    "--no-first-run",
                    "--remote-debugging-port=0",
                    f"--user-data-dir={self._profile}",
                    "about:blank",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self._port = await asyncio.to_thread(
                _read_debug_port, self._profile, self._process
            )

    async def _capture_response(self, template_id: int) -> dict:
        assert self._port is not None
        base = f"http://127.0.0.1:{self._port}"
        async with aiohttp.ClientSession() as session:
            async with session.put(f"{base}/json/new?about:blank") as response:
                target = await response.json()
            target_id = str(target["id"])
            try:
                async with session.ws_connect(target["webSocketDebuggerUrl"]) as socket:
                    command_id = 0
                    command_id = await _command(socket, command_id, "Network.enable")
                    command_id = await _command(
                        socket,
                        command_id,
                        "Network.setBlockedURLs",
                        {
                            "urls": [
                                "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif",
                                "*.woff", "*.woff2", "*.mp4", "*analytics*", "*collect*",
                            ]
                        },
                    )
                    command_id = await _command(socket, command_id, "Runtime.enable")
                    command_id = await _command(socket, command_id, "Page.enable")
                    page_url = PAGE_URL.format(template_id=template_id)
                    command_id = await _command(
                        socket, command_id, "Page.navigate", {"url": page_url}
                    )
                    return await _wait_for_dom_listings(socket, command_id)
            finally:
                await session.get(f"{base}/json/close/{target_id}")

    async def _idle_shutdown(self) -> None:
        try:
            await asyncio.sleep(self._idle_seconds)
            if self._active == 0:
                await self._stop_browser()
        except asyncio.CancelledError:
            return

    async def _stop_browser(self) -> None:
        if self._idle_task is not None and self._idle_task is not asyncio.current_task():
            self._idle_task.cancel()
        self._idle_task = None
        process = self._process
        profile = self._profile
        self._process = None
        self._profile = None
        self._port = None
        if process is not None and process.poll() is None:
            if os.name == "nt":
                await asyncio.to_thread(_kill_windows_process_tree, process.pid)
            else:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, 3)
                except subprocess.TimeoutExpired:
                    process.kill()
        if profile is not None:
            await asyncio.to_thread(shutil.rmtree, profile, True)


async def _command(
    socket: aiohttp.ClientWebSocketResponse,
    previous_id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> int:
    command_id = previous_id + 1
    await socket.send_json({"id": command_id, "method": method, "params": params or {}})
    while True:
        message = await socket.receive()
        if message.type != aiohttp.WSMsgType.TEXT:
            raise UpstreamUnavailable("youpin browser connection closed")
        payload = json.loads(message.data)
        if payload.get("id") == command_id:
            if "error" in payload:
                raise UpstreamUnavailable(str(payload["error"]))
            return command_id


DOM_LISTING_SCRIPT = """
(() => {
  const rows = [...document.querySelectorAll('tr, [role="row"]')]
    .map((row) => (row.innerText || '').replace(/\\s+/g, ' ').trim())
    .filter(Boolean);
  const priceNodes = [...document.querySelectorAll('[class*="price" i], [class*="Price"]')]
    .map((node) => '¥' + (node.textContent || '').replace(/\\s+/g, ' ').trim())
    .filter(Boolean);
  return { rows, price_nodes: priceNodes };
})()
"""


async def _wait_for_dom_listings(
    socket: aiohttp.ClientWebSocketResponse, previous_id: int
) -> dict:
    command_id = previous_id
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        command_id += 1
        await socket.send_json(
            {
                "id": command_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": DOM_LISTING_SCRIPT,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            }
        )
        while True:
            message = await socket.receive()
            if message.type != aiohttp.WSMsgType.TEXT:
                raise UpstreamUnavailable("youpin browser connection closed")
            payload = json.loads(message.data)
            if payload.get("id") != command_id:
                continue
            result = payload.get("result", {}).get("result", {})
            value = result.get("value")
            if isinstance(value, dict):
                prices = extract_dom_prices(value.get("rows", []))
                if not prices:
                    prices = extract_dom_prices(value.get("price_nodes", []))
                if prices:
                    return {"data": [{"price": price / 100} for price in prices]}
            break
        await asyncio.sleep(0.25)
    raise UpstreamUnavailable("youpin page rendered no public listings")


def extract_dom_prices(texts: list[str], limit: int = 10) -> list[int]:
    prices: list[int] = []
    for text in texts:
        for match in re.finditer(r"(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)", text):
            value = round(float(match.group(1)) * 100)
            if value > 0:
                prices.append(value)
            if len(prices) >= limit:
                return prices[:limit]
    return prices[:limit]


def _find_edge() -> Path:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise UpstreamUnavailable("Microsoft Edge is not installed")


def _cleanup_stale_profiles(max_age_seconds: int = 3600) -> None:
    cutoff = time.time() - max_age_seconds
    for profile in Path(tempfile.gettempdir()).glob("skinflow-youpin-*"):
        try:
            if profile.stat().st_mtime < cutoff:
                shutil.rmtree(profile, ignore_errors=True)
        except OSError:
            continue


def _read_debug_port(
    profile: Path, process: subprocess.Popen[bytes], timeout_seconds: float = 8.0
) -> int:
    marker = profile / "DevToolsActivePort"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise UpstreamUnavailable("Microsoft Edge exited during startup")
        if marker.exists():
            first_line = marker.read_text(encoding="utf-8").splitlines()[0]
            return int(first_line)
        time.sleep(0.05)
    raise UpstreamUnavailable("Microsoft Edge debugging port timed out")


def _kill_windows_process_tree(process_id: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(process_id), "/T", "/F"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=0x08000000,
    )
