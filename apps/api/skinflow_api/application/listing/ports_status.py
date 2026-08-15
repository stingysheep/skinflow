from __future__ import annotations

from typing import Protocol


class ListingStatusPort(Protocol):
    def list_requests(self) -> list[dict]: ...
