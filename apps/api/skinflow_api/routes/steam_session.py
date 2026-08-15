from typing import Protocol

from fastapi import APIRouter


class SteamLoginPort(Protocol):
    def status(self) -> dict: ...
    def start(self) -> dict: ...
    def clear(self) -> dict: ...


def create_steam_session_router(login: SteamLoginPort) -> APIRouter:
    router = APIRouter(prefix="/api/steam/session", tags=["steam-session"])

    @router.get("")
    def status() -> dict:
        return login.status()

    @router.post("/login", status_code=202)
    def start_login() -> dict:
        return login.start()

    @router.delete("")
    def clear_session() -> dict:
        return login.clear()

    return router
