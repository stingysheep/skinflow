from __future__ import annotations

from .ports import LedgerPort


class LedgerService:
    def __init__(self, repository: LedgerPort) -> None:
        self._repository = repository

    def holdings(self) -> list[dict]:
        return self._repository.list_holdings()

    def history(self) -> list[dict]:
        return self._repository.list_history()

    def purchase(self, **kwargs) -> dict:
        return self._repository.create_purchase(**kwargs)

    def sale(self, **kwargs) -> dict:
        return self._repository.record_sale(**kwargs)

    def receive_pending(self, **kwargs) -> dict:
        return self._repository.receive_pending_purchase(**kwargs)

    def pending(self) -> list[dict]:
        return self._repository.list_pending_purchases()

    def catalog(self, query: str = "", limit: int = 20) -> list[dict]:
        return self._repository.search_catalog(query, limit)
