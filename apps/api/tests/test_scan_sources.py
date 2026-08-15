from pathlib import Path

from skinflow_api.application.scan.models import (
    AcquisitionPlatform,
    ScanJob,
    ScanMode,
    ScanRequest,
)
from skinflow_api.infrastructure.database.sqlite_uow import SqliteScanUnitOfWork
from skinflow_api.infrastructure.platforms.csqaq.parser import parse_candidates
from skinflow_api.infrastructure.platforms.youpin.parser import parse_on_sale_response


def test_csqaq_candidate_includes_youpin_and_filter_summaries() -> None:
    candidate = parse_candidates([
        {
            "id": 1,
            "buff_id": 2,
            "yyyp_id": 3,
            "market_hash_name": "AK-47 | Slate",
            "name": "AK-47 | 板岩",
            "buff_sell_price": "10.20",
            "yyyp_sell_price": "9.80",
            "turnover_number": "42",
        }
    ])[0]

    assert candidate.name == "AK-47 | 板岩"
    assert candidate.youpin_goods_id == 3
    assert candidate.buff_summary_ask == 1020
    assert candidate.youpin_summary_ask == 980
    assert candidate.daily_volume == 42


def test_youpin_parser_groups_only_first_ten_public_listings() -> None:
    payload = {
        "Code": 0,
        "Data": {
            "CommodityList": [
                {"CommodityInfo": {"Price": price}}
                for price in ["1.12"] * 3 + ["1.13"] * 5 + ["1.16"] * 4
            ]
        },
    }

    tiers = parse_on_sale_response(payload)

    assert [(tier.price, tier.quantity) for tier in tiers] == [(112, 3), (113, 5), (116, 2)]


def test_sqlite_round_trips_scan_mode_platforms_and_filters(tmp_path: Path) -> None:
    uow = SqliteScanUnitOfWork(tmp_path / "skinflow.db")
    request = ScanRequest(
        source_mode="csqaq",
        candidate_limit=30,
        operation_mode=ScanMode.BUY_ORDER,
        acquisition_platforms=(AcquisitionPlatform.YOUPIN,),
        min_price=500,
        max_price=50_000,
        min_daily_volume=20,
    )
    job = ScanJob(request)
    uow.create_job(job)

    restored = uow.get_job(job.id)

    assert restored is not None
    assert restored.request == request
    uow.close()
