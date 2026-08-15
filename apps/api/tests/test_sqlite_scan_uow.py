from pathlib import Path

import pytest

from skinflow_api.application.scan.memory_uow import InMemoryScanUnitOfWork
from skinflow_api.application.scan.models import ScanJob, ScanRequest, ScanStatus
from skinflow_api.infrastructure.database.sqlite_uow import SqliteScanUnitOfWork


def test_sqlite_uow_persists_event_sequence_and_active_constraint(tmp_path: Path) -> None:
    uow = SqliteScanUnitOfWork(tmp_path / "skinflow.db")
    uow.enforce_single_active_job()
    job = ScanJob(ScanRequest("manual", 1, ("AK-47 | Slate",)))
    uow.create_job(job)
    job.transition(ScanStatus.RUNNING)
    uow.append_event(job, "job.started")
    events = uow.list_events(job.id)
    assert [event["sequence"] for event in events] == [1, 2]
    assert all(event["schema_version"] == 1 for event in events)
    assert uow.has_active_job()
    uow.close()


def test_memory_uow_exposes_same_event_contract() -> None:
    uow = InMemoryScanUnitOfWork()
    job = ScanJob(ScanRequest("manual", 1))
    uow.create_job(job)
    assert uow.list_events(job.id)[0]["type"] == "job.created"


def test_sqlite_allows_only_one_active_scan_across_different_statuses(tmp_path: Path) -> None:
    uow = SqliteScanUnitOfWork(tmp_path / "skinflow.db")
    uow.enforce_single_active_job()
    first = ScanJob(ScanRequest("manual", 1))
    uow.create_job(first)
    first.transition(ScanStatus.RUNNING)
    uow.append_event(first, "job.started")

    with pytest.raises(ValueError, match="active scan"):
        uow.create_job(ScanJob(ScanRequest("manual", 1)))

    uow.close()


def test_result_and_event_are_rolled_back_together(tmp_path: Path, monkeypatch) -> None:
    from skinflow_api.domain.market.snapshot import MarketSnapshot
    from skinflow_api.domain.market.tiers import MarketSide, MarketTier

    uow = SqliteScanUnitOfWork(tmp_path / "skinflow.db")
    job = ScanJob(ScanRequest("manual", 1))
    uow.create_job(job)
    job.transition(ScanStatus.RUNNING)
    uow.append_event(job, "job.started")
    snapshot = MarketSnapshot(
        "AK-47 | Slate", 1, 2, 3, None, "CNY", 730,
        (MarketTier(MarketSide.BUFF_ASK, 100, 1),), "steam-cs2-cny-v1",
    )
    original_write = uow._write_event

    def fail_result_event(job_id, sequence, event_type, payload):
        if event_type == "result.created":
            raise sqlite3.OperationalError("simulated event failure")
        original_write(job_id, sequence, event_type, payload)

    import sqlite3

    monkeypatch.setattr(uow, "_write_event", fail_result_event)
    with pytest.raises(sqlite3.OperationalError):
        uow.persist_result_and_event(job, snapshot, payload={"name": "AK-47 | Slate"})

    assert uow.list_results(job.id) == []
    assert [event["type"] for event in uow.list_events(job.id)] == ["job.created", "job.started"]
    assert uow.get_job(job.id).result_count == 0
    uow.close()


def test_sqlite_results_are_reconstructed_from_committed_snapshot(tmp_path: Path) -> None:
    from skinflow_api.domain.market.snapshot import MarketSnapshot
    from skinflow_api.domain.market.tiers import MarketSide, MarketTier
    from skinflow_api.domain.pricing.curves import CurvePoint

    uow = SqliteScanUnitOfWork(tmp_path / "skinflow.db")
    job = ScanJob(ScanRequest("manual", 1))
    uow.create_job(job)
    job.transition(ScanStatus.RUNNING)
    uow.append_event(job, "job.started")
    snapshot = MarketSnapshot(
        "AK-47 | Slate", 1, 2, 3, None, "CNY", 730,
        (
            MarketTier(MarketSide.BUFF_ASK, 100, 1),
            MarketTier(MarketSide.STEAM_BID, 200, 1),
            MarketTier(MarketSide.STEAM_ASK, 210, 1),
        ),
        "steam-cs2-cny-v1",
    )
    curve = CurvePoint(1, 100, 1_500_000, None, 1_600_000)
    job.result_count = 1
    uow.persist_result_and_event(
        job,
        snapshot,
        (curve,),
        payload={"name": "Slate", "image_url": "https://example.test/slate.png"},
    )

    assert uow.list_results(job.id) == [
        {
            "market_hash_name": "AK-47 | Slate",
            "name": "Slate",
            "image_url": "https://example.test/slate.png",
            "buff_lowest_ask": 100,
            "youpin_lowest_ask": None,
            "steam_highest_bid": 200,
            "steam_lowest_ask": 210,
            "buff_observed_at": 2,
            "youpin_observed_at": None,
            "steam_observed_at": 3,
            "daily_volume": None,
            "steam_median_price": None,
            "steam_transaction_price": None,
            "curves": [
                {
                    "quantity": 1,
                    "cost_total": 100,
                    "immediate_ratio_ppm": 1_500_000,
                    "recommended_ratio_ppm": None,
                    "market_ask_ratio_ppm": 1_600_000,
                }
            ],
        }
    ]
    uow.close()


@pytest.mark.parametrize(
    ("initial", "terminal", "event_type", "failure_code"),
    [
        (ScanStatus.QUEUED, ScanStatus.FAILED, "job.failed", "APP_RESTARTED"),
        (ScanStatus.RUNNING, ScanStatus.FAILED, "job.failed", "APP_RESTARTED"),
        (ScanStatus.CANCELLING, ScanStatus.CANCELLED, "job.cancelled", None),
    ],
)
def test_restart_recovery_is_terminal_and_persists_event(
    tmp_path: Path, initial, terminal, event_type, failure_code
) -> None:
    path = tmp_path / "skinflow.db"
    uow = SqliteScanUnitOfWork(path)
    job = ScanJob(ScanRequest("manual", 1))
    uow.create_job(job)
    if initial != ScanStatus.QUEUED:
        job.transition(ScanStatus.RUNNING)
        uow.append_event(job, "job.started")
    if initial == ScanStatus.CANCELLING:
        job.transition(ScanStatus.CANCELLING)
        uow.append_event(job, "job.cancelling")
    uow.close()

    restarted = SqliteScanUnitOfWork(path)
    assert restarted.recover_interrupted_jobs() == 1
    restarted.enforce_single_active_job()
    recovered = restarted.get_job(job.id)
    assert recovered.status == terminal
    assert recovered.failure_code == failure_code
    assert restarted.list_events(job.id)[-1]["type"] == event_type
    assert restarted.recover_interrupted_jobs() == 0
    restarted.close()
