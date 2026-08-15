import json

import pytest

from skinflow_api.application.scan.models import ScanRequest
from skinflow_api.application.scan.upstream_errors import (
    CsqaqAccessDenied,
    UpstreamUnavailable,
)
from skinflow_api.infrastructure.platforms.buff.parser import parse_sell_orders
from skinflow_api.infrastructure.platforms.csqaq.adapter import CsqaqAdapter
from skinflow_api.infrastructure.platforms.csqaq.chart import parse_chart
from skinflow_api.infrastructure.platforms.csqaq.parser import parse_candidates
from skinflow_api.infrastructure.platforms.steam.nameid_resolver import JsonNameIdResolver
from skinflow_api.infrastructure.platforms.steam.parser import parse_histogram
from skinflow_api.infrastructure.http.rate_limiter import PlatformRateLimiter


def test_csqaq_parser_skips_invalid_rows() -> None:
    result = parse_candidates([
        {"id": 1, "buff_id": 2, "market_hash_name": "AK-47 | Slate", "name": "Slate"},
        {"id": "bad", "buff_id": 0, "market_hash_name": "invalid"},
    ])
    assert len(result) == 1
    assert result[0].buff_goods_id == 2


def test_csqaq_adapter_exposes_access_denied_as_stable_error() -> None:
    class UnauthorizedClient:
        def request_json(self, *_args, **_kwargs):
            raise UpstreamUnavailable("upstream status 401", status_code=401)

    with pytest.raises(CsqaqAccessDenied) as error:
        CsqaqAdapter("token", UnauthorizedClient()).list_candidates(ScanRequest("csqaq", 20))

    assert error.value.code == "CSQAQ_ACCESS_DENIED"


def test_csqaq_candidate_source_reads_a_second_page_for_scan_backfill() -> None:
    class PagedClient:
        def __init__(self) -> None:
            self.pages: list[int] = []

        def request_json(self, _url, *, body, **_kwargs):
            self.pages.append(body["page_index"])
            if body["page_index"] == 1:
                return {"data": [{"id": 1, "buff_id": 11, "market_hash_name": "One", "buff_sell_price": 1, "turnover_number": 1}]}
            if body["page_index"] == 2:
                return {"data": [{"id": 2, "buff_id": 22, "market_hash_name": "Two", "buff_sell_price": 3, "turnover_number": 1}]}
            return {"data": []}

    client = PagedClient()
    adapter = CsqaqAdapter(
        "token", client, PlatformRateLimiter("test", concurrency=1, min_interval_seconds=0)
    )

    candidates = adapter.list_candidates(ScanRequest("csqaq", candidate_limit=1, min_price=200))

    assert [candidate.market_hash_name for candidate in candidates] == ["Two"]
    assert client.pages == [1, 2]


def test_csqaq_manual_lookup_continues_until_named_item_is_found() -> None:
    class ManualClient:
        def __init__(self) -> None:
            self.pages: list[int] = []

        def request_json(self, _url, *, body, **_kwargs):
            self.pages.append(body["page_index"])
            if body["page_index"] < 3:
                return {"data": [{"id": body["page_index"], "buff_id": 11, "market_hash_name": f"Other {body['page_index']}", "buff_sell_price": 1, "turnover_number": 1}]}
            return {"data": [{"id": 3, "buff_id": 33, "market_hash_name": "Wanted", "buff_sell_price": 1, "turnover_number": 1}]}

    client = ManualClient()
    adapter = CsqaqAdapter(
        "token", client, PlatformRateLimiter("test", concurrency=1, min_interval_seconds=0)
    )

    candidates = adapter.list_candidates(
        ScanRequest("manual", candidate_limit=1, manual_names=("Wanted",))
    )

    assert [candidate.market_hash_name for candidate in candidates] == ["Wanted"]
    assert client.pages == [1, 2, 3]


def test_csqaq_direct_lookup_resolves_items_outside_ranked_pages() -> None:
    class SearchClient:
        def request_json(self, url, **_kwargs):
            if "/search/suggest" in url:
                return {"data": [{"id": "21656", "value": "法玛斯 | 灰色幽灵 (崭新出厂)"}]}
            return {"data": {"goods_info": {
                "id": 21656,
                "market_hash_name": "FAMAS | Grey Ghost (Factory New)",
                "name": "法玛斯 | 灰色幽灵 (崭新出厂)",
                "buff_id": 1,
                "yyyp_id": 2,
                "buff_sell_price": 1,
                "yyyp_sell_price": 1,
                "steam_sell_price": 1,
                "steam_buy_price": 1,
                "turnover_number": 1,
            }}}

    candidate = CsqaqAdapter(
        "token", SearchClient(), PlatformRateLimiter("test", concurrency=1, min_interval_seconds=0)
    ).lookup_candidate("FAMAS | Grey Ghost (Factory New)", search_text="法玛斯 | 灰色幽灵")

    assert candidate is not None
    assert candidate.good_id == 21656


def test_csqaq_chart_parser_pairs_timestamp_price_and_quantity() -> None:
    points = parse_chart(
        {
            "data": {
                "timestamp": [1718726899000, 1718813206000, 1718899881000],
                "num_data": [12, 13],
                "main_data": [8350.0, 8351.0, "bad"],
            }
        }
    )
    assert points == (
        {"observed_at": 1718726899000, "value": 8350, "quantity": 12, "key": "sell_price"},
        {"observed_at": 1718813206000, "value": 8351, "quantity": 13, "key": "sell_price"},
    )


def test_csqaq_chart_parser_preserves_low_price_yuan_decimals() -> None:
    points = parse_chart(
        {"data": {"timestamp": [1, 2], "main_data": [0.31, 0.33], "num_data": [4, 5]}}
    )
    assert [point["value"] for point in points] == [31, 33]


def test_buff_parser_groups_prices_into_tiers() -> None:
    tiers = parse_sell_orders([{"price": "1.12"}, {"price": "1.12"}, {"price": "1.13"}])
    assert [(tier.price, tier.quantity) for tier in tiers] == [(112, 2), (113, 1)]


def test_steam_parser_differences_cumulative_graph() -> None:
    tiers = parse_histogram({
        "buy_order_graph": [["2.23", 1, ""], ["2.22", 3, ""]],
        "sell_order_graph": [["2.24", 2, ""], ["2.25", 5, ""]],
    })
    assert [(tier.side, tier.price, tier.quantity) for tier in tiers] == [
        ("steam_bid", 223, 1), ("steam_bid", 222, 2),
        ("steam_ask", 224, 2), ("steam_ask", 225, 3),
    ]


def test_nameid_resolver_supports_normalized_lookup(tmp_path) -> None:
    path = tmp_path / "cs2.json"
    path.write_text(json.dumps({"AK-47 | Slate": 123}), encoding="utf-8")
    assert JsonNameIdResolver(path).resolve("ak47 slate") == 123
