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

    def update_holding_average_cost(self, market_hash_name: str, cost_each: int) -> dict:
        return self._repository.update_holding_average_cost(market_hash_name, cost_each)

    def delete_holding(self, market_hash_name: str) -> dict:
        return self._repository.delete_holding(market_hash_name)
