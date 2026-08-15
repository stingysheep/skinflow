from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


class JsonPreferencesStore:
    """Small per-user store for UI preferences that must survive port changes."""

    def __init__(self, database_path: str | Path) -> None:
        database = str(database_path)
        self._path = None if database == ":memory:" else self._preferences_path(Path(database))
        self._lock = RLock()
        self._values: dict[str, Any] = self._read()

    def get(self, key: str) -> tuple[bool, Any]:
        with self._lock:
            return key in self._values, self._values.get(key)

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value
            self._write()

    def close(self) -> None:
        return None

    def _read(self) -> dict[str, Any]:
        if self._path is None or not self._path.exists():
            return {}
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._values, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, self._path)

    @staticmethod
    def _preferences_path(database: Path) -> Path:
        return database.with_name(f"{database.stem}.preferences.json")
