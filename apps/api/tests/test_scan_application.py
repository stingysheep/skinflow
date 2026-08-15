from skinflow_api.application.scan.errors import NameIdIndexUnavailable
from skinflow_api.application.scan.memory_uow import InMemoryScanUnitOfWork
from skinflow_api.application.scan.models import ScanRequest, ScanStatus
from skinflow_api.application.scan.ports import Candidate
from skinflow_api.application.scan.service import ScanService
from skinflow_api.domain.market.snapshot import MarketSnapshot
from skinflow_api.domain.market.tiers import MarketSide, MarketTier


class Candidates:
    def list_candidates(self, request, event_sink=None):
        del event_sink
        candidates = [
            Candidate("AK-47 | Slate", "AK-47 | Slate", "img", 7, 8),
            Candidate("Missing", "Missing", "", 9, 10),
        ]
        return candidates[:request.candidate_limit]


class NameIds:
    def resolve(self, name):
        return 123 if name.startswith("AK-") else None


class ChartCandidates(Candidates):
    def fetch_chart(self, good_id, *, platform, event_sink=None):
        del event_sink
        return ({"observed_at": good_id, "value": platform * 100, "quantity": 1},)


class Market:
    def fetch_snapshot(self, candidate, item_nameid, acquisition_platforms, event_sink=None):
        del acquisition_platforms, event_sink
        return MarketSnapshot(
            market_hash_name=candidate.market_hash_name,
            csqaq_observed_at=1,
            buff_observed_at=2,
            steam_observed_at=3,
            daily_volume_observed_at=4,
            currency="CNY",
            appid=730,
            fee_policy_version="steam-cs2-cny-v1",
            tiers=(
                MarketTier(MarketSide.BUFF_ASK, 112, 2),
                MarketTier(MarketSide.STEAM_BID, 223, 2),
                MarketTier(MarketSide.STEAM_ASK, 224, 2),
            ),
        )


class BrokenCandidates:
    def list_candidates(self, request, event_sink=None):
        raise RuntimeError("upstream response must not escape")


class MissingNameIdIndex:
    def resolve(self, name):
        raise NameIdIndexUnavailable()


def service():
    uow = InMemoryScanUnitOfWork()
    return ScanService(uow, Candidates(), NameIds(), Market()), uow


def test_scan_rejects_one_unresolved_candidate_but_succeeds() -> None:
    scan, uow = service()
    job = scan.create(ScanRequest("csqaq", candidate_limit=2))
    result = scan.run(job.id)

    assert result.status == ScanStatus.SUCCEEDED
    assert result.result_count == 1
    events = uow.list_events(job.id)
    assert any(event["type"] == "candidate.rejected" for event in events)
    assert all(event["schema_version"] == 1 for event in events)
    payload = next(event["payload"] for event in events if event["type"] == "result.created")
    assert payload["recommendation_price"] == 223
    assert payload["recommendation_unavailable"] is False
    assert payload["curves"][0]["recommended_ratio_ppm"] is not None


def test_result_charts_are_loaded_on_demand_for_requested_platforms() -> None:
    uow = InMemoryScanUnitOfWork()
    scan = ScanService(uow, ChartCandidates(), NameIds(), Market())
    job = scan.create(ScanRequest("csqaq", candidate_limit=1))
    scan.run(job.id)

    charts = scan.charts(job.id, "AK-47 | Slate", ("buff", "steam"))

    assert charts["buff"][0]["value"] == 100
    assert charts["steam"][0]["value"] == 300


def test_scan_cancel_from_queued_is_terminal() -> None:
    scan, _ = service()
    job = scan.create(ScanRequest("manual", candidate_limit=1, manual_names=("AK-47 | Slate",)))
    result = scan.cancel(job.id)
    assert result.status == ScanStatus.CANCELLED


def test_unhandled_failure_becomes_persisted_failed_terminal_event() -> None:
    uow = InMemoryScanUnitOfWork()
    scan = ScanService(uow, BrokenCandidates(), NameIds(), Market())
    job = scan.create(ScanRequest("csqaq", candidate_limit=1))

    result = scan.run(job.id)
    repeated = scan.run(job.id)

    assert result.status == ScanStatus.FAILED
    assert result.failure_code == "SCAN_UNEXPECTED_ERROR"
    assert repeated.status == ScanStatus.FAILED
    terminal = [event for event in uow.list_events(job.id) if event["type"] == "job.failed"]
    assert len(terminal) == 1
    assert terminal[0]["payload"]["reason_code"] == "SCAN_UNEXPECTED_ERROR"


def test_missing_nameid_index_uses_stable_configuration_failure_code() -> None:
    uow = InMemoryScanUnitOfWork()
    scan = ScanService(uow, Candidates(), MissingNameIdIndex(), Market())
    job = scan.create(ScanRequest("csqaq", candidate_limit=1))

    result = scan.run(job.id)

    assert result.status == ScanStatus.FAILED
    assert result.failure_code == "NAMEID_INDEX_UNAVAILABLE"
    assert uow.list_events(job.id)[-1]["payload"] == {
        "reason_code": "NAMEID_INDEX_UNAVAILABLE"
    }
