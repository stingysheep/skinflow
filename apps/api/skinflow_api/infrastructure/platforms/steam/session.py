from __future__ import annotations

import ctypes
import json
import os
from contextlib import suppress
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from skinflow_api.application.inventory.models import SteamSessionInfo, SteamSessionStatus


@dataclass(frozen=True, slots=True, repr=False)
class SteamCredentials:
    steamid64: str
    login_secure: str
    sessionid: str

    def __post_init__(self) -> None:
        if not self.steamid64.isdigit() or len(self.steamid64) != 17:
            raise ValueError("steamid64 must be a 17 digit Steam identifier")
        if not self.login_secure or not self.sessionid:
            raise ValueError("Steam credentials are incomplete")

    @property
    def cookie_header(self) -> str:
        return f"steamLoginSecure={self.login_secure}; sessionid={self.sessionid}"


class InMemorySteamSession:
    """Process-local Steam credentials. Values are never serialized or persisted."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._credentials: SteamCredentials | None = None
        self._expired = False

    def status(self) -> SteamSessionInfo:
        with self._lock:
            if self._credentials is None:
                return SteamSessionInfo(SteamSessionStatus.ABSENT)
            status = SteamSessionStatus.EXPIRED if self._expired else SteamSessionStatus.ACTIVE
            return SteamSessionInfo(status, self._credentials.steamid64)

    def credentials(self) -> SteamCredentials:
        with self._lock:
            if self._credentials is None or self._expired:
                raise PermissionError("Steam session is required")
            return self._credentials

    def set_credentials(self, credentials: SteamCredentials) -> None:
        with self._lock:
            self._credentials = credentials
            self._expired = False

    def mark_expired(self) -> None:
        with self._lock:
            if self._credentials is not None:
                self._expired = True

    def clear(self) -> None:
        with self._lock:
            self._credentials = None
            self._expired = False


class PersistentSteamSession(InMemorySteamSession):
    """Persist Steam cookies encrypted with Windows DPAPI for desktop restarts."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        super().__init__()
        self._path = Path(path)
        self._load()

    def set_credentials(self, credentials: SteamCredentials) -> None:
        super().set_credentials(credentials)
        self._save(credentials)

    def clear(self) -> None:
        super().clear()
        with suppress(FileNotFoundError):
            self._path.unlink()

    def _load(self) -> None:
        try:
            raw = _unprotect(self._path.read_bytes())
            value = json.loads(raw.decode("utf-8"))
            self.set_credentials(SteamCredentials(**value))
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            self.clear()

    def _save(self, credentials: SteamCredentials) -> None:
        if os.name != "nt":
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "steamid64": credentials.steamid64,
                "login_secure": credentials.login_secure,
                "sessionid": credentials.sessionid,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        temporary = self._path.with_suffix(".tmp")
        temporary.write_bytes(_protect(payload))
        temporary.replace(self._path)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is required for credential persistence")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = ctypes.create_string_buffer(value)
    source_blob = _DataBlob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    target_blob = _DataBlob()
    protected = crypt32.CryptProtectData(
        ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target_blob)
    )
    if not protected:
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(target_blob.pbData, target_blob.cbData)
    finally:
        kernel32.LocalFree(target_blob.pbData)


def _unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is required for credential persistence")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = ctypes.create_string_buffer(value)
    source_blob = _DataBlob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    target_blob = _DataBlob()
    unprotected = crypt32.CryptUnprotectData(
        ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target_blob)
    )
    if not unprotected:
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(target_blob.pbData, target_blob.cbData)
    finally:
        kernel32.LocalFree(target_blob.pbData)
