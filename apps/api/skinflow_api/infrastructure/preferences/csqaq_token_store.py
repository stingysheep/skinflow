from __future__ import annotations

import ctypes
import os
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class DpapiCsqaqTokenStore:
    """Persist the CSQAQ token outside the JSON preferences store."""

    def __init__(self, database_path: str | Path) -> None:
        database = str(database_path)
        self._path = None if database == ":memory:" else self._token_path(Path(database))

    def load(self) -> str | None:
        if self._path is None:
            return None
        try:
            value = _unprotect(self._path.read_bytes()).decode("utf-8").strip()
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            return None
        return value or None

    def save(self, token: str) -> None:
        if self._path is None:
            return
        if not token:
            self.clear()
            return
        if os.name != "nt":
            raise OSError("Windows DPAPI is required for CSQAQ token persistence")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_bytes(_protect(token.encode("utf-8")))
        temporary.replace(self._path)

    def clear(self) -> None:
        if self._path is None:
            return
        with suppress(FileNotFoundError):
            self._path.unlink()

    @staticmethod
    def _token_path(database: Path) -> Path:
        return database.with_name(f"{database.stem}.csqaq_token.bin")


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
