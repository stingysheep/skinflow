from __future__ import annotations

import asyncio

from skinflow_api.application.listing.reconciliation import ListingReconciliationService


class ListingReconciliationRunner:
    def __init__(self, service: ListingReconciliationService, interval_seconds: int = 60) -> None:
        self._service = service
        self._interval = max(15, interval_seconds)
        self._task: asyncio.Task[object] | None = None
        self._reconcile_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await self.reconcile_now()
            await asyncio.sleep(self._interval)

    async def reconcile_now(self) -> dict:
        async with self._reconcile_lock:
            return await asyncio.to_thread(self._service.reconcile)

    async def shutdown(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
