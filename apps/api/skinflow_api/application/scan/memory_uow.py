from copy import deepcopy

from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.pricing.curves import CurvePoint

from .models import ScanJob, ScanStatus


class InMemoryScanUnitOfWork:
    """Deterministic adapter for application tests; production uses SQLite."""

    def __init__(self) -> None:
        self.jobs: dict[str, ScanJob] = {}
        self.events: dict[str, list[dict]] = {}
        self.snapshots: dict[str, MarketSnapshot] = {}
        self.curves: dict[str, tuple[CurvePoint, ...]] = {}
        self.results: dict[str, list[dict]] = {}

    def has_active_job(self) -> bool:
        active = {ScanStatus.QUEUED, ScanStatus.RUNNING, ScanStatus.CANCELLING}
        return any(job.status in active for job in self.jobs.values())

    def recover_interrupted_jobs(self) -> int:
        recovered = 0
        for job in tuple(self.jobs.values()):
            if job.status in {ScanStatus.QUEUED, ScanStatus.RUNNING}:
                job.status = ScanStatus.FAILED
                job.failure_code = "APP_RESTARTED"
                self.append_event(job, "job.failed", {"reason_code": "APP_RESTARTED"})
                recovered += 1
            elif job.status == ScanStatus.CANCELLING:
                job.status = ScanStatus.CANCELLED
                self.append_event(job, "job.cancelled", {"reason_code": "APP_RESTARTED"})
                recovered += 1
        return recovered

    def create_job(self, job: ScanJob) -> None:
        if self.has_active_job():
            raise ValueError("an active scan already exists")
        self.events[job.id] = []
        self.results[job.id] = []
        self._event(job, "job.created", {})
        self.jobs[job.id] = deepcopy(job)

    def persist_result_and_event(
        self,
        job: ScanJob,
        snapshot: MarketSnapshot | None,
        curves: tuple[CurvePoint, ...] = (),
        event_type: str = "result.created",
        payload: dict | None = None,
    ) -> None:
        committed = deepcopy(job)
        if snapshot is not None:
            self.snapshots[committed.id] = snapshot
        self.curves[committed.id] = tuple(curves)
        if snapshot is not None:
            self.results[committed.id].append(deepcopy(payload or {}))
        self._event(committed, event_type, payload or {})
        self.jobs[committed.id] = deepcopy(committed)

    def append_event(self, job: ScanJob, event_type: str, payload: dict | None = None) -> None:
        committed = deepcopy(job)
        self._event(committed, event_type, payload or {})
        self.jobs[committed.id] = deepcopy(committed)

    def get_job(self, job_id: str) -> ScanJob | None:
        job = self.jobs.get(job_id)
        return deepcopy(job) if job else None

    def list_events(self, job_id: str, after: int = 0) -> list[dict]:
        return [event.copy() for event in self.events.get(job_id, []) if event["sequence"] > after]

    def list_results(self, job_id: str) -> list[dict]:
        return deepcopy(self.results.get(job_id, []))

    def _event(self, job: ScanJob, event_type: str, payload: dict) -> None:
        event = {
            "schema_version": 1,
            "job_id": job.id,
            "sequence": job.next_sequence,
            "type": event_type,
            "payload": payload,
        }
        job.next_sequence += 1
        self.events[job.id].append(event)
