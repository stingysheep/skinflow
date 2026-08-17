from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .ports import PreferencesStore

WHITELIST_IP_KEY = "csqaq.whitelist_ip"


class CsqaqTokenStore(Protocol):
    def load(self) -> str | None: ...

    def save(self, token: str) -> None: ...


class CsqaqConnection(Protocol):
    def configure(self, token: str) -> None: ...

    def validate_connection(self) -> str: ...


@dataclass(frozen=True, slots=True)
class CsqaqConfiguration:
    token_configured: bool
    whitelist_ip: str
    status: str


class CsqaqConfigurationService:
    def __init__(
        self,
        preferences: PreferencesStore,
        tokens: CsqaqTokenStore,
        connection: CsqaqConnection,
        environment_token: str,
    ) -> None:
        self._preferences = preferences
        self._tokens = tokens
        self._connection = connection
        self._environment_token = environment_token.strip()

    def status(self) -> CsqaqConfiguration:
        found, whitelist_ip = self._preferences.get(WHITELIST_IP_KEY)
        return CsqaqConfiguration(
            token_configured=bool(self._tokens.load() or self._environment_token),
            whitelist_ip=whitelist_ip.strip() if found and isinstance(whitelist_ip, str) else "",
            status=self._connection.validate_connection(),
        )

    def save(self, *, token: str | None, whitelist_ip: str) -> CsqaqConfiguration:
        if token is not None:
            normalized_token = token.strip()
            self._tokens.save(normalized_token)
            self._connection.configure(normalized_token or self._environment_token)
        self._preferences.set(WHITELIST_IP_KEY, whitelist_ip.strip())
        return self.status()
