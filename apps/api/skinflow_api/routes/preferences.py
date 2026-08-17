from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from skinflow_api.application.preferences import CsqaqConfigurationService, PreferencesStore

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


class PreferenceValue(BaseModel):
    value: Any


class CsqaqConfigurationValue(BaseModel):
    token: str | None = Field(default=None, max_length=1024)
    whitelist_ip: str = Field(default="", max_length=128)


def create_preferences_router(
    store: PreferencesStore, csqaq: CsqaqConfigurationService
) -> APIRouter:
    router = APIRouter(prefix="/api/preferences", tags=["preferences"])

    def validate_key(key: str) -> str:
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError("invalid preference key")
        return key

    @router.get("")
    def get_preferences() -> dict[str, Any]:
        return {"preferences": store.all()}

    @router.get("/csqaq")
    def get_csqaq_configuration() -> dict[str, Any]:
        return _csqaq_response(csqaq)

    @router.put("/csqaq")
    def save_csqaq_configuration(payload: CsqaqConfigurationValue) -> dict[str, Any]:
        return _csqaq_response(csqaq.save(token=payload.token, whitelist_ip=payload.whitelist_ip))

    @router.post("/csqaq/validate")
    def validate_csqaq_configuration() -> dict[str, Any]:
        return _csqaq_response(csqaq)

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


def _csqaq_response(configuration: Any) -> dict[str, Any]:
    return {
        "token_configured": configuration.token_configured,
        "whitelist_ip": configuration.whitelist_ip,
        "status": configuration.status,
    }
