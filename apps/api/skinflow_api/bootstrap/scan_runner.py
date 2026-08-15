import asyncio

from skinflow_api.application.scan.service import ScanService


class ScanTaskRunner:
    def __init__(self, service: ScanService) -> None:
        self._service = service
        self._tasks: set[asyncio.Task[object]] = set()

    def start(self, job_id: str) -> None:
        task = asyncio.create_task(asyncio.to_thread(self._service.run, job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
