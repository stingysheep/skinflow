from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.pricing.curves import CurvePoint

from .models import AcquisitionPlatform, ScanJob, ScanRequest

ScanEventSink = Callable[[str, dict], None]


@dataclass(frozen=True, slots=True)
class Candidate:
    market_hash_name: str
    name: str
    image_url: str
    buff_goods_id: int
    good_id: int
    youpin_goods_id: int = 0
    buff_summary_ask: int | None = None
    youpin_summary_ask: int | None = None
    daily_volume: int | None = None
    steam_transaction_price: int | None = None
    steam_summary_bid: int | None = None
    csqaq_url: str | None = None


class CandidateSource(Protocol):
    def list_candidates(
        self,
        request: ScanRequest,
        event_sink: ScanEventSink | None = None,
    ) -> Sequence[Candidate]: ...


class NameIdResolver(Protocol):
    def resolve(self, market_hash_name: str) -> int | None: ...


class MarketDataGateway(Protocol):
    def fetch_snapshot(
        self,
        candidate: Candidate,
        item_nameid: int,
        acquisition_platforms: tuple[AcquisitionPlatform, ...],
        event_sink: ScanEventSink | None = None,
    ) -> MarketSnapshot: ...


class ScanPersistenceUnitOfWork(Protocol):
    def recover_interrupted_jobs(self) -> int: ...

    def has_active_job(self) -> bool: ...

    def create_job(self, job: ScanJob) -> None: ...

    def persist_result_and_event(
        self,
        job: ScanJob,
        snapshot: MarketSnapshot | None,
        curves: Sequence[CurvePoint] = (),
        event_type: str = "result.created",
        payload: dict | None = None,
    ) -> None: ...

    def append_event(self, job: ScanJob, event_type: str, payload: dict | None = None) -> None: ...

    def get_job(self, job_id: str) -> ScanJob | None: ...

    def list_events(self, job_id: str, after: int = 0) -> list[dict]: ...

    def list_results(self, job_id: str) -> list[dict]: ...
