from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from skinflow_api.application.preferences import PreferencesStore

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


class PreferenceValue(BaseModel):
    value: Any


def create_preferences_router(store: PreferencesStore) -> APIRouter:
    router = APIRouter(prefix="/api/preferences", tags=["preferences"])

    def validate_key(key: str) -> str:
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError("invalid preference key")
        return key

    @router.get("")
    def get_preferences() -> dict[str, Any]:
        return {"preferences": store.all()}

    @router.get("/{key}")
    def get_preference(key: str) -> dict[str, Any]:
        key = validate_key(key)
        found, value = store.get(key)
        return {"key": key, "found": found, "value": value if found else None}

    @router.put("/{key}")
    def set_preference(key: str, payload: PreferenceValue) -> dict[str, Any]:
        key = validate_key(key)
        store.set(key, payload.value)
        return {"key": key, "saved": True}

    return router
